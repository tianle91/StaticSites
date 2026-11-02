/* Shared text normalization; address/business-name matching stays in adapters. */
const SearchQuery = {
  normalize(value) {
    return String(value ?? "")
      .toLowerCase()
      .replace(/[.,]/g, " ")
      .replace(/[\u2010-\u2015]/g, "-")
      .replace(/\s+/g, " ")
      .trim();
  },
};
