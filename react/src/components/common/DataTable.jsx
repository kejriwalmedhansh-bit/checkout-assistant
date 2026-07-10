import { Table, TableContainer, Tbody, Td, Text, Th, Thead, Tr } from '@chakra-ui/react';

import Card from './Card';

/**
 * Reusable data table. Wraps Chakra's Table in a card and scrolls horizontally
 * on small screens (responsive).
 *
 * @param {Array<{key, header, align?, width?, render?}>} columns
 *   `render(value, row)` customizes a cell; otherwise the raw value is shown.
 * @param {Array<object>} data  row objects (a `id` key is used for the React key)
 * @param {string} [emptyMessage]
 * @param {string} [minTableWidth]  min width before horizontal scroll kicks in
 */
export default function DataTable({
  columns,
  data,
  emptyMessage = 'Nothing to show yet.',
  minTableWidth = '680px',
  onRowClick,
}) {
  return (
    <Card overflow="hidden">
      <TableContainer>
        <Table variant="unstyled" minW={minTableWidth}>
          <Thead>
            <Tr borderBottom="1px solid" borderColor="border">
              {columns.map((col) => (
                <Th
                  key={col.key}
                  textAlign={col.align || 'left'}
                  w={col.width}
                  fontFamily="mono"
                  fontSize="11px"
                  fontWeight={500}
                  letterSpacing=".08em"
                  textTransform="uppercase"
                  color="text3"
                  borderColor="border"
                  py="13px"
                  px="16px"
                >
                  {col.header}
                </Th>
              ))}
            </Tr>
          </Thead>
          <Tbody>
            {data.length === 0 ? (
              <Tr>
                <Td colSpan={columns.length} px="16px" py="22px" textAlign="center">
                  <Text color="text3" fontSize="13.5px">
                    {emptyMessage}
                  </Text>
                </Td>
              </Tr>
            ) : (
              data.map((row, i) => (
                <Tr
                  key={row.id ?? i}
                  borderBottom={i === data.length - 1 ? 'none' : '1px solid'}
                  borderColor="border"
                  transition="background .12s"
                  _hover={{ bg: 'surface2' }}
                  cursor={onRowClick ? 'pointer' : undefined}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                >
                  {columns.map((col) => (
                    <Td
                      key={col.key}
                      textAlign={col.align || 'left'}
                      borderColor="border"
                      py="14px"
                      px="16px"
                      fontSize="13.5px"
                      color="text"
                      whiteSpace={col.whiteSpace}
                      wordBreak={col.whiteSpace === 'normal' ? 'break-word' : undefined}
                    >
                      {col.render ? col.render(row[col.key], row) : row[col.key]}
                    </Td>
                  ))}
                </Tr>
              ))
            )}
          </Tbody>
        </Table>
      </TableContainer>
    </Card>
  );
}
