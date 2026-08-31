import { Box, Flex, Text } from '@chakra-ui/react';

import BackButton from '@/components/common/BackButton';
import { usePageHeader } from '@/hooks/usePageHeader';
import { ROUTES } from '@/routes/paths';

/**
 * Shared shell for static content pages (About, Contact, Privacy, Terms,
 * brand pages) — the same card/back-button frame HowItWorksPage uses, so
 * these read as part of the product rather than a bolted-on legal appendix.
 */
export default function InfoPageShell({ title, subtitle, maxW = '680px', children }) {
  const backControl = <BackButton fallback={ROUTES.home} iconOnly />;
  usePageHeader({ left: backControl });

  return (
    <Box maxW={maxW} mx="auto">
      <Flex display={{ base: 'none', lg: 'flex' }} align="center" gap="6px" mb="14px">
        {backControl}
      </Flex>

      <Box
        bg="surface"
        border="1px solid"
        borderColor="border"
        borderRadius="28px"
        boxShadow="0 1px 2px rgba(22,32,43,.06), 0 24px 52px -20px rgba(22,32,43,.24)"
        px={{ base: '22px', md: '40px' }}
        py={{ base: '30px', md: '38px' }}
      >
        <Box mb="28px">
          <Text as="h1" m="0 0 9px" fontSize={{ base: '26px', md: '32px' }} fontWeight={800} letterSpacing="-.025em" lineHeight={1.1}>
            {title}
          </Text>
          {subtitle && (
            <Text fontSize="14px" color="text2" lineHeight={1.55} maxW="480px">
              {subtitle}
            </Text>
          )}
        </Box>

        {children}
      </Box>
    </Box>
  );
}
