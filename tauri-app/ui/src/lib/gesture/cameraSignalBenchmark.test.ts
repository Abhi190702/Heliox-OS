import { describe, expect, it } from "vitest";
import { benchmarkCameraSignals, type CameraSignalFrame } from "./cameraSignalBenchmark";

function frame(overrides: Partial<CameraSignalFrame>): CameraSignalFrame {
  return {
    timestampMs: 0,
    expectedHand: false,
    predictedHand: false,
    expectedGesture: null,
    predictedGesture: null,
    expectedGaze: null,
    predictedGaze: null,
    ...overrides,
  };
}

describe("benchmarkCameraSignals", () => {
  it("reports false hand/gesture activations and gaze stability over recorded time", () => {
    const report = benchmarkCameraSignals([
      frame({ timestampMs: 0, expectedGaze: "center", predictedGaze: "center" }),
      frame({
        timestampMs: 20_000,
        expectedHand: true,
        predictedHand: true,
        expectedGesture: "palm",
        predictedGesture: "palm",
        expectedGaze: "right",
        predictedGaze: "right",
      }),
      frame({
        timestampMs: 40_000,
        expectedHand: false,
        predictedHand: true,
        predictedGesture: "thumbs_up",
        expectedGaze: "right",
        predictedGaze: "center",
      }),
      frame({
        timestampMs: 60_000,
        expectedHand: true,
        predictedHand: false,
        expectedGesture: "fist",
        expectedGaze: null,
        predictedGaze: null,
      }),
    ]);

    expect(report.frameCount).toBe(4);
    expect(report.durationMs).toBe(60_000);
    expect(report.handPresence).toMatchObject({ truePositive: 1, falsePositive: 1, falseNegative: 1 });
    expect(report.gestureEvents).toMatchObject({
      truePositive: 1,
      falsePositive: 1,
      falseNegative: 1,
      falseActivationsPerMinute: 1,
    });
    expect(report.gaze).toMatchObject({
      labeledFrames: 3,
      negativeFrames: 1,
      coverage: 1,
      accuracy: 2 / 3,
      rejectionSpecificity: 1,
      expectedTransitions: 1,
      predictedTransitions: 2,
      excessTransitionsPerMinute: 1,
    });
  });

  it("returns perfect empty-class scores instead of NaN", () => {
    const report = benchmarkCameraSignals([frame({ timestampMs: 0 }), frame({ timestampMs: 1_000 })]);
    expect(report.handPresence).toMatchObject({ precision: 1, recall: 1, f1: 1 });
    expect(report.gestureEvents).toMatchObject({ precision: 1, recall: 1, f1: 1 });
    expect(report.gaze.rejectionSpecificity).toBe(1);
    expect(Number.isFinite(report.gaze.excessTransitionsPerMinute)).toBe(true);
  });

  it("rejects missing, duplicate, reversed, and non-finite timestamps", () => {
    expect(() => benchmarkCameraSignals([])).toThrow("at least two");
    expect(() => benchmarkCameraSignals([frame({ timestampMs: 1 }), frame({ timestampMs: 1 })])).toThrow(
      "strictly increasing",
    );
    expect(() => benchmarkCameraSignals([frame({ timestampMs: 2 }), frame({ timestampMs: 1 })])).toThrow(
      "strictly increasing",
    );
    expect(() => benchmarkCameraSignals([frame({ timestampMs: 1 }), frame({ timestampMs: Number.NaN })])).toThrow(
      "strictly increasing",
    );
  });
});
