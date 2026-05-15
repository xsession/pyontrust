import { useMemo } from "react";
import type { BoardSummary } from "../contracts/api";
import { VirtualizedTreeList, type VirtualizedTreeListSection } from "../shared/ui/virtualized/VirtualizedTreeList";

interface VirtualBoardListProps {
  boards: BoardSummary[];
  selectedBoardId: string;
  onSelectBoard: (boardId: string) => void;
}

export function VirtualBoardList({ boards, selectedBoardId, onSelectBoard }: VirtualBoardListProps) {
  const selectedBoard = boards.find((board) => board.id === selectedBoardId || board.board === selectedBoardId) ?? null;
  const sections = useMemo<VirtualizedTreeListSection<BoardSummary>[]>(() => {
    const nextSections: VirtualizedTreeListSection<BoardSummary>[] = [];
    if (selectedBoard) {
      nextSections.push({
        id: "selected-board",
        label: "Pinned board",
        items: [selectedBoard],
        meta: selectedBoard.package,
      });
    }

    const groups = new Map<string, BoardSummary[]>();
    boards.forEach((board) => {
      if (selectedBoard && board.id === selectedBoard.id) {
        return;
      }

      const packageGroup = groups.get(board.package) ?? [];
      packageGroup.push(board);
      groups.set(board.package, packageGroup);
    });

    groups.forEach((groupBoards, packageName) => {
      nextSections.push({
        id: `package:${packageName}`,
        label: packageName,
        items: groupBoards,
        meta: `${groupBoards.length} boards`,
        collapsible: true,
      });
    });

    return nextSections;
  }, [boards, selectedBoard]);

  return (
    <VirtualizedTreeList
      ariaLabel="Board inventory"
      sections={sections}
      getItemId={(board) => board.id}
      estimatedRowHeight={96}
      overscan={5}
      viewportClassName="board-list-viewport"
      dataTestId="virtual-board-list"
      renderItem={({ item: board }) => {
        const selected = selectedBoardId === board.id || selectedBoardId === board.board;

        return (
          <article className="board-list__item">
            <button
              type="button"
              className={`board-list__button${selected ? " board-list__button--selected" : ""}`}
              onClick={() => onSelectBoard(board.board)}
            >
              <strong>{board.name}</strong>
              <span>{board.board}</span>
              <span>{board.package} • {board.pin_count} pins</span>
            </button>
          </article>
        );
      }}
    />
  );
}