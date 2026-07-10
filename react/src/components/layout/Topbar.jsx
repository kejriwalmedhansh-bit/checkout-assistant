import { Flex, Text } from '@chakra-ui/react';

export default function Topbar({ title, badge, meta, children }) {
  return (
    <Flex
      as="header"
      align="flex-start"
      justify="space-between"
      gap="12px"
      pb={{ base: '14px', md: '18px' }}
      mb={{ base: '20px', md: '28px' }}
      mx={{ base: '-16px', md: '-34px' }}
      px={{ base: '16px', md: '34px' }}
      borderBottom="1px solid"
      borderColor="border"
      flexWrap="wrap"
    >
      <Flex direction="column" minW={0} gap="3px">
        <Flex align="center" gap="10px" flexWrap="wrap">
          <Text
            m={0}
            fontSize={{ base: '16px', md: '18px' }}
            fontWeight={700}
            lineHeight={1.25}
          >
            {title}
          </Text>
          {badge}
        </Flex>
        {meta && (
          <Text m={0} color="text2" fontSize="13px" fontWeight={400} lineHeight={1.5}>
            {meta}
          </Text>
        )}
      </Flex>
      {children && (
        <Flex align="center" gap="10px" flexWrap="wrap">
          {children}
        </Flex>
      )}
    </Flex>
  );
}
