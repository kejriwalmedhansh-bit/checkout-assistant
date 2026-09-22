/**
 * The voucher sites Dealo reads, by the `voucher_source` the API sends.
 * One list for every screen — the results page used to know only two
 * names and called every BuyHatke voucher "Gyftr", sending people to look
 * on the wrong site.
 */
export const VOUCHER_SOURCE_NAMES = { gyftr: 'Gyftr', maximize: 'Maximize', buyhatke: 'BuyHatke' };

export const voucherSourceName = (source) => VOUCHER_SOURCE_NAMES[source] || 'Gyftr';
