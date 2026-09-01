import { useState } from 'react';
import { Box, Flex } from '@chakra-ui/react';

// The long-tail store list (900+) deliberately has no real logos —
// sourcing/hosting logo images at that scale raises trademark questions
// this project isn't positioned to clear brand-by-brand. A deterministic
// colour + initials fallback (same pattern Slack/GitHub use for avatars)
// scans just as fast without that risk. The small flagship set can pass a
// real `logoSrc` (provided directly by the brand/product owner, not
// scraped) — this component falls back to the initials treatment
// automatically if that image 404s, so a missing file never breaks layout.
const COLORS = ['brand', 'brass', 'cyan', 'green', 'violet', 'amber'];

function hashName(name) {
  let h = 0;
  for (let i = 0; i < name.length; i += 1) {
    h = (h * 31 + name.charCodeAt(i)) >>> 0;
  }
  return h;
}

function initialsFor(name) {
  const words = name.trim().split(/\s+/).slice(0, 2);
  return words.map((w) => w[0]).join('').toUpperCase();
}

export default function BrandAvatar({ name, size = 36, radius, fontSize, logoSrc }) {
  const [imgFailed, setImgFailed] = useState(false);
  const resolvedRadius = radius || `${Math.round(size * 0.3)}px`;

  if (logoSrc && !imgFailed) {
    return (
      <Flex
        w={`${size}px`}
        h={`${size}px`}
        flex="0 0 auto"
        align="center"
        justify="center"
        borderRadius={resolvedRadius}
        bg="surface"
        border="1px solid"
        borderColor="border"
        overflow="hidden"
        p={`${Math.round(size * 0.12)}px`}
      >
        <Box
          as="img"
          src={logoSrc}
          alt={`${name} logo`}
          w="100%"
          h="100%"
          objectFit="contain"
          onError={() => setImgFailed(true)}
        />
      </Flex>
    );
  }

  const color = COLORS[hashName(name) % COLORS.length];
  return (
    <Flex
      w={`${size}px`}
      h={`${size}px`}
      flex="0 0 auto"
      align="center"
      justify="center"
      borderRadius={resolvedRadius}
      bg={color}
      color="onBrand"
      fontWeight={800}
      fontSize={fontSize || `${Math.round(size * 0.38)}px`}
    >
      {initialsFor(name)}
    </Flex>
  );
}
