import { useState } from 'react';
import { Button, Flex, Input } from '@chakra-ui/react';

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

  const submit = () => {
    const q = value.trim();
    if (!q || isLoading) return;
    onSubmit?.(q);
  };

  const h = size === 'lg' ? '52px' : '44px';

  return (
    <Flex
      as="form"
      gap="8px"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <Input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={placeholder}
        h={h}
        flex={1}
        autoComplete="off"
        aria-label="Search for a product"
      />
      <Button
        type="submit"
        variant="primary"
        h={h}
        px="22px"
        isDisabled={isLoading || !value.trim()}
        leftIcon={<I.search size={17} />}
      >
        {isLoading ? 'Searching…' : buttonLabel}
      </Button>
    </Flex>
  );
}
