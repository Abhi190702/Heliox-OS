import type { GazeRegion } from "./gazeTracking";

export interface CameraSignalFrame {
  timestampMs: number;
  expectedHand: boolean;
  predictedHand: boolean;
  expectedGesture: string | null;
  predictedGesture: string | null;
  expectedGaze: GazeRegion | null;
  predictedGaze: GazeRegion | null;
}

export interface ClassificationMetrics {
  truePositive: number;
  falsePositive: number;
  falseNegative: number;
  precision: number;
  recall: number;
  f1: number;
}

export interface CameraSignalBenchmarkReport {
  frameCount: number;
  durationMs: number;
  handPresence: ClassificationMetrics;
  gestureEvents: ClassificationMetrics & { falseActivationsPerMinute: number };
  gaze: {
    labeledFrames: number;
    negativeFrames: number;
    coverage: number;
    accuracy: number;
    rejectionSpecificity: number;
    expectedTransitions: number;
    predictedTransitions: number;
    excessTransitionsPerMinute: number;
  };
}

function ratio(numerator: number, denominator: number, emptyValue = 1): number {
  return denominator === 0 ? emptyValue : numerator / denominator;
}

function classificationMetrics(
  truePositive: number,
  falsePositive: number,
  falseNegative: number,
): ClassificationMetrics {
  const precision = ratio(truePositive, truePositive + falsePositive);
  const recall = ratio(truePositive, truePositive + falseNegative);
  return {
    truePositive,
    falsePositive,
    falseNegative,
    precision,
    recall,
    f1: precision + recall === 0 ? 0 : (2 * precision * recall) / (precision + recall),
  };
}

function transitionCount(values: Array<GazeRegion | null>): number {
  let transitions = 0;
  let previous: GazeRegion | null = null;
  for (const value of values) {
    if (value === null) continue;
    if (previous !== null && value !== previous) transitions++;
    previous = value;
  }
  return transitions;
}

/**
 * Scores recorded detector output without invoking camera, cursor, workflow,
 * or daemon actions. Callers remain responsible for lawful dataset use and
 * for keeping raw biometric media outside committed fixtures.
 */
export function benchmarkCameraSignals(frames: CameraSignalFrame[]): CameraSignalBenchmarkReport {
  if (frames.length < 2) throw new Error("Camera benchmark requires at least two timestamped frames");
  for (let index = 0; index < frames.length; index++) {
    const timestamp = frames[index].timestampMs;
    if (!Number.isFinite(timestamp) || (index > 0 && timestamp <= frames[index - 1].timestampMs)) {
      throw new Error("Camera benchmark timestamps must be finite and strictly increasing");
    }
  }

  const durationMs = frames.at(-1)!.timestampMs - frames[0].timestampMs;
  const minutes = durationMs / 60_000;

  let handTruePositive = 0;
  let handFalsePositive = 0;
  let handFalseNegative = 0;
  let gestureTruePositive = 0;
  let gestureFalsePositive = 0;
  let gestureFalseNegative = 0;
  let gazeLabeled = 0;
  let gazeNegative = 0;
  let gazeCovered = 0;
  let gazeCorrect = 0;
  let gazeRejectedNegative = 0;

  for (const frame of frames) {
    if (frame.expectedHand && frame.predictedHand) handTruePositive++;
    else if (!frame.expectedHand && frame.predictedHand) handFalsePositive++;
    else if (frame.expectedHand && !frame.predictedHand) handFalseNegative++;

    if (frame.expectedGesture && frame.predictedGesture === frame.expectedGesture) gestureTruePositive++;
    else {
      if (frame.predictedGesture) gestureFalsePositive++;
      if (frame.expectedGesture) gestureFalseNegative++;
    }

    if (frame.expectedGaze) {
      gazeLabeled++;
      if (frame.predictedGaze) gazeCovered++;
      if (frame.predictedGaze === frame.expectedGaze) gazeCorrect++;
    } else {
      gazeNegative++;
      if (frame.predictedGaze === null) gazeRejectedNegative++;
    }
  }

  const handPresence = classificationMetrics(handTruePositive, handFalsePositive, handFalseNegative);
  const gestureEvents = classificationMetrics(gestureTruePositive, gestureFalsePositive, gestureFalseNegative);
  const expectedTransitions = transitionCount(frames.map((frame) => frame.expectedGaze));
  const predictedTransitions = transitionCount(frames.map((frame) => frame.predictedGaze));

  return {
    frameCount: frames.length,
    durationMs,
    handPresence,
    gestureEvents: {
      ...gestureEvents,
      falseActivationsPerMinute: gestureFalsePositive / minutes,
    },
    gaze: {
      labeledFrames: gazeLabeled,
      negativeFrames: gazeNegative,
      coverage: ratio(gazeCovered, gazeLabeled),
      accuracy: ratio(gazeCorrect, gazeLabeled),
      rejectionSpecificity: ratio(gazeRejectedNegative, gazeNegative),
      expectedTransitions,
      predictedTransitions,
      excessTransitionsPerMinute: Math.max(0, predictedTransitions - expectedTransitions) / minutes,
    },
  };
}
