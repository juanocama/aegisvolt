import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { App } from "./main";

describe("AegisVolt app", () => {
  it("fails closed when test is selected", async () => {
    vi.stubGlobal("fetch", vi.fn());
    render(<App />);

    const testButton = screen.getByRole("button", { name: "test" });
    fireEvent.click(testButton);

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Environment endpoint not configured"),
    );
  });
});
