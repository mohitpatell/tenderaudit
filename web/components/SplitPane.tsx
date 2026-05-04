"use client";

import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from "@/components/ui/resizable";

interface SplitPaneProps {
  left: React.ReactNode;
  right: React.ReactNode;
  defaultLeftPercent?: number;
}

export function SplitPane({ left, right, defaultLeftPercent = 50 }: SplitPaneProps) {
  return (
    <ResizablePanelGroup direction="horizontal" className="flex-1 min-h-0">
      <ResizablePanel defaultSize={defaultLeftPercent} minSize={25}>
        <div className="h-full overflow-auto">{left}</div>
      </ResizablePanel>
      <ResizableHandle withHandle />
      <ResizablePanel defaultSize={100 - defaultLeftPercent} minSize={25}>
        <div className="h-full overflow-auto">{right}</div>
      </ResizablePanel>
    </ResizablePanelGroup>
  );
}
