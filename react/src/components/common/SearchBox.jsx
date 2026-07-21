import { useRef, useState } from 'react';
import { Box, Button, Flex, Input, InputGroup, InputRightElement } from '@chakra-ui/react';

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
 */
export default function SearchBox({
  initialValue = '',
  onSubmit,
  isLoading = false,
  placeholder = 'Paste a product link or type what you want to buy…',
  buttonLabel = 'Find the best deal',
  size = 'lg',
}) {
  const [value, setValue] = useState(initialValue);
  const inputRef = useRef(null);

  const submit = () => {
    const q = value.trim();
    if (!q || isLoading) return;
    onSubmit?.(q);
  };

  const clear = () => {
    setValue('');
    inputRef.current?.focus();
  };

  const h = size === 'lg' ? '52px' : '44px';

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
          onChange={(e) => setValue(e.target.value)}
          placeholder={placeholder}
          h={h}
          pr={value ? '38px' : undefined}
          autoComplete="off"
          aria-label="Search for a product"
        />
        {value && (
          <InputRightElement h={h} w="38px">
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
          </InputRightElement>
        )}
      </InputGroup>
      <Button
        type="submit"
        variant="primary"
        h={h}
        px="22px"
        w={{ base: '100%', md: 'auto' }}
        flex={{ base: 'none', md: '0 0 auto' }}
        isDisabled={isLoading || !value.trim()}
        leftIcon={<I.search size={17} />}
      >
        {isLoading ? 'Searching…' : buttonLabel}
      </Button>
    </Flex>
  );
}
