import { useEffect, useRef, useState } from 'react';
import { Box, Button, Flex, Input, InputGroup, InputRightElement, Text } from '@chakra-ui/react';
import { useReducedMotion } from 'framer-motion';

import { I } from './icons';

/**
 * Controlled search input + submit button. Used both by the hero on SearchPage
 * and the compact re-run bar on ResultsPage.
 *
 * @param {string}   initialValue   prefill (e.g. the last query)
 * @param {(q:string)=>void} onSubmit  called with the trimmed query (never empty)
 * @param {boolean}  isLoading      disables the button + shows a busy label
 * @param {string}   placeholder
 * @param {string}   buttonLabel
 * @param {'lg'|'md'} size          visual size preset
 * @param {string[]} hints          example searches shown one after another in
 *                                  the empty box ("Try: Nike Air Force 1"), typed
 *                                  out letter by letter; replaces `placeholder`
 * @param {string}   emptyMessage   shown when the button is tapped with an empty box
 */

// Typing speed for the example searches: quick enough to feel alive, slow
// enough to read. Pauses on each finished example before rubbing it out.
const TYPE_MS = 70;
const ERASE_MS = 30;
const HOLD_MS = 1600;

/** Cycles through `hints`, typing each one out. Stops while the box has focus
 *  or text, so it never moves under someone's thumb. */
function useTypedHint(hints, paused) {
  const reduce = useReducedMotion();
  const [text, setText] = useState(hints?.[0] ?? '');
  useEffect(() => {
    if (!hints?.length || paused) return undefined;
    if (reduce) {
      // No typing animation: swap whole examples every few seconds instead.
      let i = 0;
      setText(hints[0]);
      const t = setInterval(() => { i = (i + 1) % hints.length; setText(hints[i]); }, 3000);
      return () => clearInterval(t);
    }
    let wi = 0;
    let ci = 0;
    let erasing = false;
    let timer;
    const step = () => {
      const word = hints[wi];
      if (!erasing) {
        ci += 1;
        if (ci >= word.length) { erasing = true; setText(word); timer = setTimeout(step, HOLD_MS); return; }
      } else {
        ci -= 1;
        if (ci <= 0) { erasing = false; wi = (wi + 1) % hints.length; }
      }
      setText(word.slice(0, ci));
      timer = setTimeout(step, erasing ? ERASE_MS : TYPE_MS);
    };
    step();
    return () => clearTimeout(timer);
  }, [hints, paused, reduce]);
  return text;
}
export default function SearchBox({
  initialValue = '',
  onSubmit,
  isLoading = false,
  placeholder = 'Product name or paste a link',
  buttonLabel = 'Find the best deal',
  size = 'lg',
  hints,
  emptyMessage = 'Type a product name or paste a link',
}) {
  const [value, setValue] = useState(initialValue);
  const [focused, setFocused] = useState(false);
  const [nudge, setNudge] = useState(false);
  const inputRef = useRef(null);
  const hint = useTypedHint(hints, focused || !!value);

  useEffect(() => {
    if (!nudge) return undefined;
    const t = setTimeout(() => setNudge(false), 2400);
    return () => clearTimeout(t);
  }, [nudge]);

  const submit = () => {
    const q = value.trim();
    if (isLoading) return;
    if (!q) {
      // The button always looks ready (a greyed-out one read as broken, and
      // 121 of 316 visitors left without a tap, 9–14 Nov). Tapping it with an
      // empty box points at the box instead of doing nothing.
      setNudge(true);
      inputRef.current?.focus();
      return;
    }
    // Close the phone keyboard before the page changes, so the next page
    // opens at full height instead of squeezed above a keyboard.
    inputRef.current?.blur();
    onSubmit?.(q);
  };

  const clear = () => {
    setValue('');
    inputRef.current?.focus();
  };

  const paste = async () => {
    const tryRead = async () => {
      try {
        return await navigator.clipboard.readText();
      } catch {
        return '';
      }
    };

    let text = await tryRead();
    if (!text) {
      // iOS Safari's first-ever readText() often comes back empty at the
      // exact moment the user taps "Allow Paste" on its native prompt — the
      // permission is granted but that first call already settled without
      // it. One retry, after the grant has landed, picks up the real value
      // instead of making the user tap the button a second time.
      await new Promise((resolve) => setTimeout(resolve, 150));
      text = await tryRead();
    }
    if (text) setValue(text);
    inputRef.current?.focus();
  };

  const h = size === 'lg' ? '52px' : '44px';
  const rightElementW = value ? '76px' : '38px';

  return (
    <Flex
      as="form"
      // Side-by-side on every screen used to mean the button (fixed width,
      // set by its own icon+label) claimed a much bigger share of a narrow
      // phone screen than of a wide desktop one — the input was left with
      // whatever sliver remained, sometimes narrower than the button itself.
      // Stacking on mobile gives the input the full width on its own line
      // regardless of device size.
      direction={{ base: 'column', md: 'row' }}
      wrap={{ base: 'nowrap', md: 'wrap' }}
      gap="8px"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <InputGroup flex={1} minW={0}>
        <Input
          ref={inputRef}
          value={value}
          onChange={(e) => { setValue(e.target.value); setNudge(false); }}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder={hints?.length && !focused ? `Try: ${hint}` : placeholder}
          borderColor={nudge ? 'brass' : undefined}
          focusBorderColor={nudge ? 'brass' : undefined}
          _focusVisible={nudge ? { borderColor: 'brass', boxShadow: '0 0 0 3px var(--chakra-colors-brassSoft)' } : undefined}
          boxShadow={nudge ? '0 0 0 3px var(--chakra-colors-brassSoft)' : undefined}
          h={h}
          pr={rightElementW}
          autoComplete="off"
          aria-label="Search for a product"
        />
        <InputRightElement h={h} w={rightElementW} gap="2px" justifyContent="flex-end" pr="7px">
          {value && (
            <Box
              as="button"
              type="button"
              onClick={clear}
              aria-label="Clear search"
              display="inline-flex"
              alignItems="center"
              justifyContent="center"
              w="24px"
              h="24px"
              borderRadius="50%"
              color="text2"
              _hover={{ color: 'text', bg: 'borderStrong' }}
              _focusVisible={{ outline: '2px solid currentColor', outlineOffset: '2px' }}
            >
              <I.x size={15} />
            </Box>
          )}
          <Box
            as="button"
            type="button"
            onClick={paste}
            aria-label="Paste from clipboard"
            display="inline-flex"
            alignItems="center"
            justifyContent="center"
            w="24px"
            h="24px"
            borderRadius="50%"
            color="text2"
            _hover={{ color: 'text', bg: 'borderStrong' }}
            _focusVisible={{ outline: '2px solid currentColor', outlineOffset: '2px' }}
          >
            <I.paste size={15} />
          </Box>
        </InputRightElement>
      </InputGroup>
      <Button
        type="submit"
        variant="primary"
        h={h}
        px="22px"
        w={{ base: '100%', md: 'auto' }}
        flex={{ base: 'none', md: '0 0 auto' }}
        isDisabled={isLoading}
        leftIcon={<I.search size={17} />}
      >
        {isLoading ? 'Searching…' : buttonLabel}
      </Button>
      {nudge && (
        <Text role="status" fontSize="12.5px" color="#8A4A17" textAlign="center" w="100%" m={0}>
          {emptyMessage}
        </Text>
      )}
    </Flex>
  );
}
