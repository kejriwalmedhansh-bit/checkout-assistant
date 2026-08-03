import { useLayoutEffect, useRef, useState } from 'react';
import { Box, Flex } from '@chakra-ui/react';

/**
 * One step's full detail on screen at a time, changed by a horizontal drag
 * or by JourneyChips above — the fix for "scrolling down through three
 * fully-expanded steps causes drop-off". Direct manipulation while
 * dragging (the panel tracks the pointer live, not just at release) rather
 * than a step you can only advance via a button.
 *
 * All three panels sit side by side in one row so the drag can move between
 * them, which means a plain flex row would size itself to the *tallest*
 * panel always — leaving visible blank space under any shorter one. The
 * wrapper's height is measured off the active panel specifically and
 * applied explicitly instead, animated on change.
 */
export default function JourneyPanels({ activeIndex, onChangeIndex, children }) {
  const count = children.length;
  const containerRef = useRef(null);
  const panelRefs = useRef([]);
  const [height, setHeight] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [dragDelta, setDragDelta] = useState(0);
  const startX = useRef(0);

  useLayoutEffect(() => {
    const active = panelRefs.current[activeIndex];
    if (active) setHeight(active.scrollHeight);
  }, [activeIndex, children]);

  // A press that starts on a link or button is that control's, not the
  // panel's: capturing the pointer here would retarget the follow-up click
  // to this container, so the CTA never navigated at all. Swiping still
  // works from anywhere else on the card.
  const onPointerDown = (e) => {
    if (e.target?.closest?.('a, button, input, select, textarea, [role="button"]')) return;
    setDragging(true);
    startX.current = e.clientX;
    setDragDelta(0);
    e.currentTarget.setPointerCapture(e.pointerId);
  };
  const onPointerMove = (e) => {
    if (!dragging) return;
    setDragDelta(e.clientX - startX.current);
  };
  const endDrag = () => {
    if (!dragging) return;
    setDragging(false);
    const width = containerRef.current?.offsetWidth || 1;
    const threshold = width * 0.18;
    if (dragDelta < -threshold && activeIndex < count - 1) onChangeIndex(activeIndex + 1);
    else if (dragDelta > threshold && activeIndex > 0) onChangeIndex(activeIndex - 1);
    setDragDelta(0);
  };

  const width = containerRef.current?.offsetWidth || 1;
  const basePct = -(activeIndex * 100);
  const dragPct = (dragDelta / width) * 100;

  return (
    <Box>
      <Box
        ref={containerRef}
        overflow="hidden"
        borderRadius="16px"
        position="relative"
        h={height != null ? `${height}px` : 'auto'}
        transition={dragging ? 'none' : 'height 300ms cubic-bezier(.16,1,.3,1)'}
      >
        <Box
          display="flex"
          alignItems="flex-start"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={endDrag}
          onPointerCancel={endDrag}
          sx={{
            transform: `translateX(${basePct + dragPct}%)`,
            transition: dragging ? 'none' : 'transform 360ms cubic-bezier(.16,1,.3,1)',
            touchAction: 'pan-y',
            cursor: dragging ? 'grabbing' : 'grab',
            '@media (prefers-reduced-motion: reduce)': dragging ? {} : { transition: 'none' },
          }}
        >
          {children.map((child, i) => (
            <Box key={i} ref={(el) => (panelRefs.current[i] = el)} flex="0 0 100%" minW="0">
              {child}
            </Box>
          ))}
        </Box>
      </Box>

      {/* Swipe isn't discoverable on its own — a small dot per step, same
          count as the cards, makes "there's more, keep going" obvious. */}
      <Flex justify="center" align="center" gap="6px" mt="12px">
        {children.map((_, i) => (
          <Box
            key={i}
            w={i === activeIndex ? '16px' : '6px'}
            h="6px"
            borderRadius="99px"
            bg={i === activeIndex ? 'brand' : 'border'}
            transition="width .25s ease, background .25s ease"
          />
        ))}
      </Flex>
    </Box>
  );
}
