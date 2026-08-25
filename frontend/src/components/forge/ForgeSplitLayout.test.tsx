import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ForgeSplitLayout } from "./ForgeSplitLayout";

afterEach(() => {
  cleanup();
});

describe("ForgeSplitLayout", () => {
  it("applies stage-open class and three-track grid when stage is open", () => {
    const { container } = render(
      <ForgeSplitLayout
        stageOpen
        left={<div>chat-panel</div>}
        right={<div>stage-panel</div>}
      />,
    );
    const split = container.querySelector(".gf-forge-split");
    expect(split).toHaveClass("gf-forge-split--stage-open");
    const cols = (split as HTMLElement).style.gridTemplateColumns;
    expect(cols).toContain("6px");
    expect(cols).toContain("minmax(0, 1fr)");
    expect(screen.getByText("chat-panel")).toBeInTheDocument();
    expect(screen.getByText("stage-panel")).toBeInTheDocument();
  });

  it("does not mount the stage panel when closed", () => {
    render(
      <ForgeSplitLayout
        stageOpen={false}
        left={<div>chat-only</div>}
        right={<div>stage-hidden</div>}
      />,
    );
    expect(screen.getByText("chat-only")).toBeInTheDocument();
    expect(screen.queryByText("stage-hidden")).not.toBeInTheDocument();
  });
});
