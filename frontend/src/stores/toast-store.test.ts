import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useToastStore, toast } from "./toast-store";

describe("toast-store", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    useToastStore.getState().clear();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("默认 duration 后自动消失", () => {
    toast.error("boom");
    expect(useToastStore.getState().toasts).toHaveLength(1);
    vi.advanceTimersByTime(5001);
    expect(useToastStore.getState().toasts).toHaveLength(0);
  });

  it("duration=0 不自动消失", () => {
    toast.info("stay", 0);
    vi.advanceTimersByTime(10000);
    expect(useToastStore.getState().toasts).toHaveLength(1);
  });

  it("同 message 去重", () => {
    toast.error("dup");
    toast.error("dup");
    toast.error("dup");
    expect(useToastStore.getState().toasts).toHaveLength(1);
  });

  it("堆叠上限 4", () => {
    for (let i = 0; i < 10; i++) toast.error(`msg-${i}`);
    expect(useToastStore.getState().toasts).toHaveLength(4);
  });

  it("dismiss 清指定 id", () => {
    const id = toast.info("x", 0);
    useToastStore.getState().dismiss(id);
    expect(useToastStore.getState().toasts).toHaveLength(0);
  });
});
