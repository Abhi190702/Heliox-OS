/**
 * Coarse, on-device gaze-region estimation from MediaPipe Tasks-Vision's
 * FaceLandmarker output (478-point face mesh with iris refinement).
 *
 * Deliberately NOT pixel-precise pointing — a consumer webcam has no IR
 * eye-tracker hardware, and pixel-accurate gaze estimation from RGB alone
 * needs a real per-user calibration routine this module doesn't attempt.
 * Instead, this reports one of five coarse regions (center/left/right/up/
 * down) from the iris's position within each eye socket, relative to that
 * eye's own corner/eyelid landmarks — a "which rough direction is the user
 * looking" signal, not "which pixel." See GESTURES.md's gaze-tracking
 * section for how this feeds the multimodal fusion engine as a passive
 * disambiguating signal alongside voice + gesture, never as a standalone
 * command trigger on its own.
 *
 * Pure geometry, no MediaPipe/DOM dependency — testable in isolation from
 * the camera/component, same pattern as spatialModel.ts/worldModel.ts.
 *
 * Privacy: this function's only output is a coarse region label + a
 * confidence float — never raw landmarks. GestureControl.svelte sends only
 * that label to the backend, never face geometry or video frames,
 * mirroring how gesture events already send just a gesture name.
 */

export interface FaceLandmark {
  x: number;
  y: number;
  z?: number;
}

export type GazeRegion = "center" | "left" | "right" | "up" | "down";

export interface GazeEstimate {
  region: GazeRegion;
  confidence: number;
}

export type GazeRejectionReason =
  "missing_face" | "invalid_landmarks" | "eyes_closed" | "head_turn" | "inconsistent_eyes" | "iris_outside_eye";

export interface GazeFrameAssessment {
  estimate: GazeEstimate | null;
  reason: GazeRejectionReason | null;
  quality: number;
}

export interface GazeBlendshape {
  categoryName: string;
  score: number;
}

export interface StabilizedGaze {
  estimate: GazeEstimate | null;
  state: "stable" | "settling" | "rejected";
  reason: GazeRejectionReason | null;
  candidateRegion: GazeRegion | null;
}

export type HandTrackingBackend = "legacy" | "tasks";

/** Legacy Hands and Tasks-Vision cannot safely coexist because both WASM
 * bundles install an Emscripten `Module` global. A gaze session therefore
 * keeps both hand and face models on Tasks-Vision. */
export function resolveHandBackend(
  configured: HandTrackingBackend | undefined,
  gazeEnabled: boolean,
): HandTrackingBackend {
  return gazeEnabled || configured === "tasks" ? "tasks" : "legacy";
}

/** A live camera must be rebuilt before switching between the incompatible
 * legacy Hands and Tasks-Vision WASM runtimes. */
export function cameraBackendNeedsRestart(
  cameraActive: boolean,
  cameraStarting: boolean,
  activeBackend: HandTrackingBackend,
  configuredBackend: HandTrackingBackend | undefined,
  gazeEnabled: boolean,
): boolean {
  return cameraActive && !cameraStarting && activeBackend !== resolveHandBackend(configuredBackend, gazeEnabled);
}

// Fusion only considers readings inside its short correlation window. A
// steady gaze therefore needs a heartbeat as well as change-based updates;
// otherwise an unchanged region silently expires after the first event.
export const GAZE_HEARTBEAT_MS = 750;

/**
 * FaceLandmarker is substantially more expensive when a face is present
 * because it emits the full 478-point mesh. Running it every sixth camera
 * frame can monopolize the UI thread and starve HandLandmarker, especially
 * on CPU-only systems. Two gaze samples per second are sufficient for the
 * coarse fusion signal and leave hand/cursor tracking responsive.
 */
export const GAZE_INFERENCE_INTERVAL_MS = 500;

/** MediaPipe's video examples guard inference with video.currentTime so a
 * 60 Hz animation loop does not synchronously process the same 30 fps camera
 * frame twice. The first decoded frame is always eligible. */
export function shouldRunVideoInference(currentVideoTime: number, previousVideoTime: number): boolean {
  return Number.isFinite(currentVideoTime) && currentVideoTime >= 0 && currentVideoTime !== previousVideoTime;
}

export function shouldRunGazeInference(nowMs: number, previousRunAtMs: number): boolean {
  return nowMs - previousRunAtMs >= GAZE_INFERENCE_INTERVAL_MS;
}

export function shouldSendGazeUpdate(
  region: GazeRegion,
  previousRegion: GazeRegion | null,
  nowMs: number,
  previousSentAtMs: number,
): boolean {
  return region !== previousRegion || nowMs - previousSentAtMs >= GAZE_HEARTBEAT_MS;
}

// MediaPipe's 478-point face mesh topology (iris refinement enabled) —
// fixed indices, not derived at runtime.
const LEFT_EYE = { iris: 468, outer: 33, inner: 133, top: 159, bottom: 145 };
const RIGHT_EYE = { iris: 473, outer: 263, inner: 362, top: 386, bottom: 374 };
const MIN_LANDMARK_COUNT = 478;
const MIN_EYE_APERTURE_RATIO = 0.08;
const MIN_PROJECTED_EYE_SYMMETRY = 0.45;
const MAX_HORIZONTAL_EYE_DISAGREEMENT = 0.28;
const MAX_VERTICAL_EYE_DISAGREEMENT = 0.35;
const IRIS_SOCKET_PADDING = 0.15;
const BLINK_REJECTION_SCORE = 0.55;

// Approximate — not tuned against a real webcam/real users. A dead zone
// around the eye socket's geometric center absorbs normal jitter and head
// micro-movement so "center" doesn't flicker to a side reading on every
// frame. Revisit against real usage, same caveat as every other
// empirically-tuned threshold in this gesture pipeline (spatialModel.ts,
// worldModel.ts) that hasn't been validated against real camera data yet.
const HORIZONTAL_DEADZONE = 0.15;
const VERTICAL_DEADZONE = 0.15;

interface EyeRatio {
  horizontal: number; // 0..1 across the eye socket, not screen-relative
  vertical: number; // 0..1 across the eye socket, not screen-relative
}

function eyeGazeRatio(
  landmarks: FaceLandmark[],
  eye: { iris: number; outer: number; inner: number; top: number; bottom: number },
): EyeRatio {
  const iris = landmarks[eye.iris];
  const outer = landmarks[eye.outer];
  const inner = landmarks[eye.inner];
  const top = landmarks[eye.top];
  const bottom = landmarks[eye.bottom];

  const minX = Math.min(outer.x, inner.x);
  const width = Math.abs(inner.x - outer.x) || 1e-6;
  const horizontal = (iris.x - minX) / width;

  const minY = Math.min(top.y, bottom.y);
  const height = Math.abs(bottom.y - top.y) || 1e-6;
  const vertical = (iris.y - minY) / height;

  return { horizontal, vertical };
}

function clamp01(value: number): number {
  return Math.max(0, Math.min(1, value));
}

function blendshapeScore(blendshapes: GazeBlendshape[] | undefined, name: string): number {
  return blendshapes?.find((shape) => shape.categoryName === name)?.score ?? 0;
}

function rejection(reason: GazeRejectionReason): GazeFrameAssessment {
  return { estimate: null, reason, quality: 0 };
}

export function gazeRejectionMessage(reason: GazeRejectionReason): string {
  switch (reason) {
    case "missing_face":
      return "Gaze is on, but no face is visible to the camera.";
    case "invalid_landmarks":
      return "Face found, but the eye landmarks are incomplete.";
    case "eyes_closed":
      return "Gaze paused while your eyes are closed or blinking.";
    case "head_turn":
      return "Gaze paused because one eye is too foreshortened; face the camera more directly.";
    case "inconsistent_eyes":
      return "Gaze is stabilizing because the two eye readings disagree.";
    case "iris_outside_eye":
      return "Gaze paused because the iris landmarks are outside a plausible eye region.";
  }
}

/** Estimates a coarse gaze region from a full 478-point FaceLandmarker
 * reading (raw, unmirrored camera-frame landmark space — same convention
 * GestureControl.svelte's cursor bridge already flips for display, see
 * its "Coordinate mapping" note). Returns null if the landmark array isn't
 * a full face mesh reading (e.g. no face detected this frame). */
function estimateGazeRegionUnchecked(landmarks: FaceLandmark[] | null | undefined): GazeEstimate | null {
  if (!landmarks || landmarks.length < MIN_LANDMARK_COUNT) return null;

  const left = eyeGazeRatio(landmarks, LEFT_EYE);
  const right = eyeGazeRatio(landmarks, RIGHT_EYE);

  // Average both eyes — more robust than trusting one alone, since a head
  // turn can foreshorten/occlude one eye's landmarks more than the other.
  const horizontal = (left.horizontal + right.horizontal) / 2;
  const vertical = (left.vertical + right.vertical) / 2;

  const dx = horizontal - 0.5;
  const dy = vertical - 0.5;

  if (Math.abs(dx) < HORIZONTAL_DEADZONE && Math.abs(dy) < VERTICAL_DEADZONE) {
    const maxDeadzone = Math.max(HORIZONTAL_DEADZONE, VERTICAL_DEADZONE);
    const confidence = 1 - Math.max(Math.abs(dx), Math.abs(dy)) / maxDeadzone;
    return { region: "center", confidence };
  }

  // Plus-shaped discretization (not a full 3x3 grid): whichever axis
  // deviates further from center wins, deliberately not trying to resolve
  // diagonal corners precisely — simpler and more robust to webcam noise.
  if (Math.abs(dx) > Math.abs(dy)) {
    return { region: dx > 0 ? "right" : "left", confidence: Math.min(1, Math.abs(dx) / 0.5) };
  }
  return { region: dy > 0 ? "down" : "up", confidence: Math.min(1, Math.abs(dy) / 0.5) };
}

/**
 * Rejects low-quality face frames before they can enter multimodal fusion.
 * These checks may only remove or reduce a reading; they never manufacture
 * a direction or increase its confidence.
 */
export function assessGazeFrame(
  landmarks: FaceLandmark[] | null | undefined,
  blendshapes?: GazeBlendshape[],
): GazeFrameAssessment {
  if (!landmarks || landmarks.length < MIN_LANDMARK_COUNT) return rejection("missing_face");

  const required = [
    LEFT_EYE.iris,
    LEFT_EYE.outer,
    LEFT_EYE.inner,
    LEFT_EYE.top,
    LEFT_EYE.bottom,
    RIGHT_EYE.iris,
    RIGHT_EYE.outer,
    RIGHT_EYE.inner,
    RIGHT_EYE.top,
    RIGHT_EYE.bottom,
  ];
  if (
    required.some((index) => {
      const point = landmarks[index];
      return !point || !Number.isFinite(point.x) || !Number.isFinite(point.y) || !Number.isFinite(point.z ?? 0);
    })
  ) {
    return rejection("invalid_landmarks");
  }

  const leftWidth = Math.abs(landmarks[LEFT_EYE.inner].x - landmarks[LEFT_EYE.outer].x);
  const rightWidth = Math.abs(landmarks[RIGHT_EYE.inner].x - landmarks[RIGHT_EYE.outer].x);
  const leftHeight = Math.abs(landmarks[LEFT_EYE.bottom].y - landmarks[LEFT_EYE.top].y);
  const rightHeight = Math.abs(landmarks[RIGHT_EYE.bottom].y - landmarks[RIGHT_EYE.top].y);
  if (Math.min(leftWidth, rightWidth, leftHeight, rightHeight) < 1e-5) return rejection("invalid_landmarks");

  const blinkScore = Math.max(
    blendshapeScore(blendshapes, "eyeBlinkLeft"),
    blendshapeScore(blendshapes, "eyeBlinkRight"),
  );
  const aperture = Math.min(leftHeight / leftWidth, rightHeight / rightWidth);
  if (blinkScore >= BLINK_REJECTION_SCORE || aperture < MIN_EYE_APERTURE_RATIO) return rejection("eyes_closed");

  const projectedEyeSymmetry = Math.min(leftWidth, rightWidth) / Math.max(leftWidth, rightWidth);
  if (projectedEyeSymmetry < MIN_PROJECTED_EYE_SYMMETRY) return rejection("head_turn");

  const left = eyeGazeRatio(landmarks, LEFT_EYE);
  const right = eyeGazeRatio(landmarks, RIGHT_EYE);
  if (
    [left.horizontal, left.vertical, right.horizontal, right.vertical].some(
      (ratio) => ratio < -IRIS_SOCKET_PADDING || ratio > 1 + IRIS_SOCKET_PADDING,
    )
  ) {
    return rejection("iris_outside_eye");
  }

  const horizontalDisagreement = Math.abs(left.horizontal - right.horizontal);
  const verticalDisagreement = Math.abs(left.vertical - right.vertical);
  if (
    horizontalDisagreement > MAX_HORIZONTAL_EYE_DISAGREEMENT ||
    verticalDisagreement > MAX_VERTICAL_EYE_DISAGREEMENT
  ) {
    return rejection("inconsistent_eyes");
  }

  const apertureQuality = clamp01((aperture - MIN_EYE_APERTURE_RATIO) / 0.12);
  const symmetryQuality = clamp01(projectedEyeSymmetry / 0.8);
  const agreementQuality = clamp01(
    1 -
      Math.max(
        horizontalDisagreement / MAX_HORIZONTAL_EYE_DISAGREEMENT,
        verticalDisagreement / MAX_VERTICAL_EYE_DISAGREEMENT,
      ),
  );
  const quality = Math.min(apertureQuality, symmetryQuality, agreementQuality);
  const estimate = estimateGazeRegionUnchecked(landmarks);
  if (!estimate) return rejection("invalid_landmarks");

  return {
    estimate: { ...estimate, confidence: clamp01(estimate.confidence * quality) },
    reason: null,
    quality,
  };
}

export function estimateGazeRegion(landmarks: FaceLandmark[] | null | undefined): GazeEstimate | null {
  return assessGazeFrame(landmarks).estimate;
}

/** Two-sample hysteresis for region changes. A blink or rejected frame never
 * refreshes stale gaze context, and a one-frame boundary wobble cannot flip
 * the region sent to the daemon. */
export class GazeTemporalStabilizer {
  private stable: GazeEstimate | null = null;
  private pendingRegion: GazeRegion | null = null;
  private pendingCount = 0;

  observe(assessment: GazeFrameAssessment): StabilizedGaze {
    if (!assessment.estimate) {
      this.pendingRegion = null;
      this.pendingCount = 0;
      return { estimate: null, state: "rejected", reason: assessment.reason, candidateRegion: null };
    }

    const next = assessment.estimate;
    if (!this.stable) {
      this.stable = next;
      return { estimate: next, state: "stable", reason: null, candidateRegion: next.region };
    }
    if (next.region === this.stable.region) {
      this.pendingRegion = null;
      this.pendingCount = 0;
      this.stable = {
        region: next.region,
        confidence: this.stable.confidence * 0.6 + next.confidence * 0.4,
      };
      return { estimate: this.stable, state: "stable", reason: null, candidateRegion: next.region };
    }

    if (next.region === this.pendingRegion) this.pendingCount += 1;
    else {
      this.pendingRegion = next.region;
      this.pendingCount = 1;
    }
    if (this.pendingCount < 2) {
      return { estimate: null, state: "settling", reason: null, candidateRegion: next.region };
    }

    this.stable = next;
    this.pendingRegion = null;
    this.pendingCount = 0;
    return { estimate: next, state: "stable", reason: null, candidateRegion: next.region };
  }

  reset(): void {
    this.stable = null;
    this.pendingRegion = null;
    this.pendingCount = 0;
  }
}
