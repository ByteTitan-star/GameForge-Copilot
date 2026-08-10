import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Toaster } from "./Toaster";
import { useToastStore, toast } from "@/stores/toast-store";

describe("Toaster", () => {
  beforeEach(() => {
    useToastStore.getState().clear();
  });
  afterEach(() => {
    cleanup();
    useToastStore.getState().clear();
  });

  it("error toast 渲染为 alert 含文案", () => {
    toast.error("出错了", 0);
    render(<Toaster />);
    expect(screen.getByRole("alert")).toHaveTextContent("出错了");
  });

  it("点击关闭按钮移除 toast", async () => {
    const user = userEvent.setup();
    toast.error("出错了", 0);
    render(<Toaster />);
    await user.click(screen.getByRole("button"));
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
