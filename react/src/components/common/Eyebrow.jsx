import { Text } from '@chakra-ui/react';

/** Small uppercase mono label — the design's `.eyebrow`. */
export default function Eyebrow(props) {
  return (
    <Text
      as="span"
      fontFamily="mono"
      fontSize="11px"
      letterSpacing=".14em"
      textTransform="uppercase"
      color="text3"
      fontWeight={500}
      whiteSpace="nowrap"
      {...props}
    />
  );
}
