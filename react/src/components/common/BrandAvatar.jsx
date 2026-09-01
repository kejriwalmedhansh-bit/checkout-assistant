import { Flex } from '@chakra-ui/react';

// Deliberately not real brand logos — sourcing/hosting logo images for 900+
// brands raises trademark questions this project isn't positioned to clear
// brand-by-brand. A deterministic colour + initials fallback (same pattern
// Slack/GitHub use for avatars) scans just as fast without that risk.
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

export default function BrandAvatar({ name, size = 36, radius, fontSize }) {
  const color = COLORS[hashName(name) % COLORS.length];
  return (
    <Flex
      w={`${size}px`}
      h={`${size}px`}
      flex="0 0 auto"
      align="center"
      justify="center"
      borderRadius={radius || `${Math.round(size * 0.3)}px`}
      bg={color}
      color="onBrand"
      fontWeight={800}
      fontSize={fontSize || `${Math.round(size * 0.38)}px`}
    >
      {initialsFor(name)}
    </Flex>
  );
}
