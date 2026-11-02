/* Keep this helper project-local. House numbers are identifiers, not substrings. */
const FeatureSearch = (() => {
  const normalize = SearchQuery.normalize;
  function compile(value) {
    const query = normalize(value);
    // A house number (with optional street text) must match as a complete
    // identifier. Street-name-only queries can still be partial while typing.
    const address = query.match(/^(\d+[a-z]?(?:-\d+[a-z]?)?)(?:\s+([a-z].*))?$/);
    return (street) => {
      if (!query) return true;
      const normalized = normalize(street);
      if (address) {
        const split = normalized.indexOf(" ");
        const number = split < 0 ? normalized : normalized.slice(0, split);
        return number === address[1] &&
          (!address[2] || (split >= 0 && normalized.slice(split + 1).startsWith(address[2])));
      }
      return normalized.includes(query);
    };
  }
  return { normalize, compile };
})();
