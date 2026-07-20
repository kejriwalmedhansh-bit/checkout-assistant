/**
 * Button — rounded-rectangle looks:
 *  - `primary`: brand CTA (no shadow)
 *  - `ghost`:   white/surface with a strong border (secondary action)
 *  - `iconSubtle`: borderless icon button used in the sidebar / topbar
 *
 * Buttons carry NO drop shadow (only the focus-visible a11y ring). Heights vary
 * per usage; pass `h` to override the default without leaving the variant.
 */
export const buttonTheme = {
  baseStyle: {
    fontFamily: 'body',
    fontWeight: 600,
    fontSize: '14.5px',
    borderRadius: 'sm',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '8px',
    h: '44px',
    px: '20px',
    lineHeight: 1,
    whiteSpace: 'nowrap',
    transitionProperty: 'common',
    transitionDuration: 'fast',
    _active: { transform: 'translateY(1px) scale(0.99)' },
    _focusVisible: { boxShadow: 'ring' },
    _disabled: { opacity: 0.55, cursor: 'not-allowed', boxShadow: 'none' },
  },
  variants: {
    primary: {
      bg: 'brand',
      color: 'onBrand',
      boxShadow: 'none',
      _hover: { bg: 'brandHover', _disabled: { bg: 'brand' } },
      _active: { bg: 'brandHover' },
    },
    ghost: {
      bg: 'surface',
      color: 'text',
      border: '1px solid',
      borderColor: 'borderStrong',
      boxShadow: 'none',
      _hover: { bg: 'surface3', _disabled: { bg: 'surface' } },
    },
    iconSubtle: {
      bg: 'transparent',
      color: 'text2',
      boxShadow: 'none',
      _hover: { bg: 'surface3', color: 'text' },
    },
    danger: {
      bg: 'transparent',
      color: 'danger',
      border: '1px solid',
      borderColor: 'danger',
      boxShadow: 'none',
      _hover: { bg: 'surface3' },
    },
  },
  defaultProps: { variant: 'ghost' },
};
