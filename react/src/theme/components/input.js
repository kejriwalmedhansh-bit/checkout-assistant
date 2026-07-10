/**
 * Form fields — clean white fill, light border, rounded corners, and a brand
 * focus ring (border + soft glow). Shared by <Input /> and <Textarea /> so both
 * look identical. Applied as the default variant so plain elements just work.
 */
const fieldStyles = {
  bg: 'surface',
  border: '1px solid',
  borderColor: 'border',
  borderRadius: 'sm',
  fontSize: '15px',
  color: 'text',
  _placeholder: { color: 'text3', fontSize: '13.5px' },
  _hover: { borderColor: 'borderStrong' },
  _focus: { borderColor: 'orange', boxShadow: 'ring', bg: 'surface' },
  _focusVisible: { borderColor: 'orange', boxShadow: 'ring', bg: 'surface' },
};

export const inputTheme = {
  variants: {
    field: { field: { ...fieldStyles, h: '48px', px: '14px' } },
  },
  defaultProps: { variant: 'field' },
};

export const textareaTheme = {
  variants: {
    outline: { ...fieldStyles, px: '14px', py: '12px', minH: '112px' },
  },
  defaultProps: { variant: 'outline' },
};
