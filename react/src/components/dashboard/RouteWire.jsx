import { Box } from '@chakra-ui/react';

/**
 * The connector between the savings node and the step card below it —
 * plugs the reward directly into the route instead of leaving them as two
 * separate blocks with a gap (and a sentence explaining the gap) between
 * them. `animated` draws a slow single current flowing downward; callers
 * should pass `false` when `prefers-reduced-motion` is set, same as every
 * other motion in this app.
 */
export default function RouteWire({ animated = true }) {
  return (
    <Box h="20px" pl="34px">
      <Box
        w="2px"
        h="100%"
        bgImage="linear-gradient(var(--chakra-colors-green) 55%, rgba(0,0,0,0) 0%)"
        bgSize="2px 10px"
        bgRepeat="repeat-y"
        sx={
          animated
            ? {
                animation: 'dealo-wire-flow 1.1s linear infinite',
                '@keyframes dealo-wire-flow': {
                  from: { backgroundPositionY: '0px' },
                  to: { backgroundPositionY: '10px' },
                },
              }
            : undefined
        }
      />
    </Box>
  );
}
