import { Box, forwardRef } from '@chakra-ui/react';

/** Surface card — the design's `.card`. Override any prop (padding, bg, etc.). */
const Card = forwardRef((props, ref) => (
  <Box
    ref={ref}
    bg="surface"
    border="1px solid"
    borderColor="border"
    borderRadius="md"
    boxShadow="sm"
    {...props}
  />
));

Card.displayName = 'Card';
export default Card;
