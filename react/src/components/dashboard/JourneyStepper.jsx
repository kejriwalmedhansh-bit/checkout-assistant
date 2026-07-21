import { Box, Flex, Grid, Text } from '@chakra-ui/react';

/** Tone → accent color when a step is the current one. Matches the tone
 * each step already carries in JourneySpotlight (voucher = amber, everything
 * else = brand green) so the two stay visually paired. */
const TONE_COLOR = { brand: 'brand', voucher: 'amber', checkout: 'brand' };

function StepDot({ done, current, tone }) {
  const color = TONE_COLOR[tone] || 'brand';
  return (
    <Flex
      w="30px"
      h="30px"
      flex="0 0 auto"
      borderRadius="50%"
      align="center"
      justify="center"
      border="2px solid"
      borderColor={done ? 'brand' : current ? color : 'borderStrong'}
      bg={done ? 'brand' : current ? `${color}Soft` : 'surface3'}
      color={done ? 'onBrand' : current ? color : 'text2'}
      fontSize="12px"
      fontWeight={700}
      fontFamily="mono"
      transition="background .2s, border-color .2s, color .2s"
      position="relative"
      zIndex={1}
    >
      {done ? (
        <Box as="svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" w="14px" h="14px">
          <path d="M5 13l4 4L19 7" />
        </Box>
      ) : (
        '•'
      )}
    </Flex>
  );
}

/**
 * Horizontal "step X of N" progress header — the whole journey visible in one
 * glance, so completing a step visibly advances a shared line rather than
 * just ticking an isolated row. Only meaningful when there's more than one
 * step (a direct-buy route with no voucher skips this entirely).
 */
export default function JourneyStepper({ steps, currentKey }) {
  const currentIndex = steps.findIndex((s) => s.key === currentKey);

  return (
    <Box mb="16px">
      <Grid templateColumns={steps.map(() => '30px').join(' 1fr ')} alignItems="center">
        {steps.map((s, i) => {
          const done = i < currentIndex;
          const current = i === currentIndex;
          return (
            <Box key={s.key} display="contents">
              <StepDot done={done} current={current} tone={s.tone} />
              {i < steps.length - 1 && (
                <Box h="2px" bg={i < currentIndex ? 'brand' : 'borderStrong'} transition="background .3s" />
              )}
            </Box>
          );
        })}
      </Grid>
      <Grid templateColumns={`repeat(${steps.length}, 1fr)`} mt="6px">
        {steps.map((s, i) => (
          <Text
            key={s.key}
            fontSize="10.5px"
            fontWeight={600}
            color="text3"
            textAlign={i === 0 ? 'left' : i === steps.length - 1 ? 'right' : 'center'}
          >
            {s.label}
          </Text>
        ))}
      </Grid>
    </Box>
  );
}
