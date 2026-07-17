/**
 * Switch — brand track when on, neutral border-strong when off.
 */
export const switchTheme = {
  baseStyle: {
    track: {
      bg: 'borderStrong',
      _checked: { bg: 'brand' },
      _focusVisible: { boxShadow: 'ring' },
    },
  },
};
