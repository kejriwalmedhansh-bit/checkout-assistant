import { Flex, Text } from '@chakra-ui/react';

import { fmt } from '@/utils/format';

/**
 * The amount drawn the way Maximize's own card page draws it: a 64 × 36 tile,
 * 8 px corners, 14 px medium, navy when chosen (measured on their sandbox,
 * 30 Oct 2026). Maximize's frame cannot take the amount from Dealo, so the
 * shopper picks it there; showing the same shape here first means they look
 * for a picture they have already seen, not for words. "× 2" when Dealo's
 * answer is several vouchers of one amount (Maximize sells one amount per
 * order, up to four of it).
 */
export function MaximizePieces({ denominations, scale = 1, onDark = false }) {
  const piece = denominations?.[0];
  if (!piece) return null;
  const w = Math.round(64 * scale);
  const h = Math.round(36 * scale);
  return (
    <Flex as="span" display="inline-flex" align="center" gap={`${Math.round(8 * scale)}px`}>
      <Flex
        as="span"
        w={`${w}px`}
        h={`${h}px`}
        flex="0 0 auto"
        borderRadius={`${Math.round(8 * scale)}px`}
        bg={onDark ? 'white' : '#293142'}
        color={onDark ? '#293142' : 'white'}
        fontSize={`${Math.round(14 * scale)}px`}
        fontWeight={500}
        align="center"
        justify="center"
        aria-label={`${fmt(piece.amount)} voucher`}
      >
        {fmt(piece.amount)}
      </Flex>
      {piece.count > 1 && (
        <Text as="span" fontFamily="mono" fontWeight={700} fontSize={`${Math.round(16 * scale)}px`} opacity={onDark ? 0.9 : 1}>
          × {piece.count}
        </Text>
      )}
    </Flex>
  );
}
