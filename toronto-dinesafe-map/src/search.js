/* Keep this helper project-local. House numbers are identifiers, not substrings. */
const FeatureSearch = (() => {
  const normalize = SearchQuery.normalize;
  function compile(value, { addressOnly = true } = {}) {
    const query = normalize(value);
    // Full permit numbers begin with two numeric groups, so they stay in the
    // general text search. A number followed by street text is address-only.
    const address = query.match(/^(\d+[a-z]?(?:-\d+[a-z]?)?)\s+([a-z].*)$/);
    return (street, ...text) => {
      if (!query) return true;
      const normalized = normalize(street);
      if (address) {
        const split = normalized.indexOf(" ");
        if (
          split > 0 && normalized.slice(0, split) === address[1] &&
          normalized.slice(split + 1).startsWith(address[2])
        ) return true;
        if (addressOnly) return false;
        // DineSafe also has numeric business names (e.g. "3 Brewers"). Keep
        // these searchable without matching an 8 embedded in a name's 38.
        return text.some((value) => {
          const name = normalize(value);
          let at = name.indexOf(query);
          while (at !== -1) {
            if (!at || !/[a-z0-9]/.test(name[at - 1])) return true;
            at = name.indexOf(query, at + 1);
          }
          return false;
        });
      }
      return normalized.includes(query) || text.some((s) => normalize(s).includes(query));
    };
  }
  return { normalize, compile };
})();
