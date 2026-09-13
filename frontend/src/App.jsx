import { useMemo, useState } from "react";
import "./App.css";

const API_BASE_URL = "http://localhost:8000";

const Icon = ({ name, size = 18 }) => {
  const paths = {
    search: (
      <>
        <circle cx="11" cy="11" r="7" />
        <path d="m20 20-3.2-3.2" />
      </>
    ),
    document: (
      <>
        <path d="M7 3h7l4 4v14H7z" />
        <path d="M14 3v5h5" />
        <path d="M10 12h5M10 16h5" />
      </>
    ),
    target: (
      <>
        <circle cx="12" cy="12" r="8" />
        <circle cx="12" cy="12" r="3" />
        <path d="M18 6 21 3M18 3h3v3" />
      </>
    ),
    pin: (
      <>
        <path d="M12 21s6-5.2 6-11a6 6 0 1 0-12 0c0 5.8 6 11 6 11Z" />
        <circle cx="12" cy="10" r="2" />
      </>
    ),
    tag: (
      <>
        <path d="M20 13 13 20a2 2 0 0 1-2.8 0L4 13.8V4h9.8L20 10.2a2 2 0 0 1 0 2.8Z" />
        <circle cx="9" cy="9" r="1.5" />
      </>
    ),
    home: (
      <>
        <path d="m3 11 9-7 9 7" />
        <path d="M5 10v10h14V10M9 20v-6h6v6" />
      </>
    ),
    bed: (
      <>
        <path d="M3 19v-8M21 19v-8M3 16h18M6 11V7h5a3 3 0 0 1 3 3v1M3 13h18" />
      </>
    ),
    bath: (
      <>
        <path d="M4 12h16v2a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5v-2Z" />
        <path d="M7 12V6a3 3 0 0 1 6 0" />
      </>
    ),
    sparkle: (
      <>
        <path d="m12 3 1.3 3.7L17 8l-3.7 1.3L12 13l-1.3-3.7L7 8l3.7-1.3L12 3Z" />
        <path d="m19 14 .7 2.3L22 17l-2.3.7L19 20l-.7-2.3L16 17l2.3-.7L19 14Z" />
        <path d="m5 15 .8 2.2L8 18l-2.2.8L5 21l-.8-2.2L2 18l2.2-.8L5 15Z" />
      </>
    ),
    shield: (
      <>
        <path d="M12 3 5 6v5c0 4.6 2.8 8.1 7 10 4.2-1.9 7-5.4 7-10V6l-7-3Z" />
        <path d="m9 12 2 2 4-4" />
      </>
    ),
    heart: <path d="M20.8 5.8a5.5 5.5 0 0 0-7.8 0L12 6.8l-1-1a5.5 5.5 0 1 0-7.8 7.8L12 22l8.8-8.4a5.5 5.5 0 0 0 0-7.8Z" />,
    chevron: <path d="m6 9 6 6 6-6" />,
  };

  return (
    <svg
      className="icon"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name]}
    </svg>
  );
};

const getFirstValue = (object, keys) => {
  for (const key of keys) {
    const value = object?.[key];
    if (value !== undefined && value !== null && value !== "") return value;
  }
  return "";
};

const toPrettyLabel = (value) =>
  String(value)
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

const formatPrice = (value) => {
  if (value === "" || value === null || value === undefined) return "";
  const numeric = Number(String(value).replace(/[$,]/g, ""));
  if (Number.isNaN(numeric)) return String(value);
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(numeric);
};

const formatBackendValue = (key, value) => {
  if (value === null || value === undefined || value === "") return "Not specified";

  if (Array.isArray(value)) {
    return value.length
      ? value.map((item) => toPrettyLabel(item)).join(", ")
      : "None";
  }

  if (typeof value === "boolean") return value ? "Yes" : "No";

  if (/price/i.test(key) && !Number.isNaN(Number(value))) {
    return formatPrice(value);
  }

  if (typeof value === "string") return toPrettyLabel(value);
  return String(value);
};

const buildQueryParsingDisplay = (filters) => {
  const safeFilters =
    filters && typeof filters === "object" && !Array.isArray(filters)
      ? filters
      : {};

  const formatRange = ({ exactKey, minKey, maxKey, isPrice = false }) => {
    const exact = safeFilters[exactKey];
    const min = safeFilters[minKey];
    const max = safeFilters[maxKey];
    const formatValue = (value) => (isPrice ? formatPrice(value) : String(value));

    if (exact !== undefined && exact !== null && exact !== "") {
      return formatValue(exact);
    }

    if (
      min !== undefined &&
      min !== null &&
      min !== "" &&
      max !== undefined &&
      max !== null &&
      max !== ""
    ) {
      return `${formatValue(min)} – ${formatValue(max)}`;
    }

    if (min !== undefined && min !== null && min !== "") {
      return isPrice ? `At least ${formatValue(min)}` : `${formatValue(min)}+`;
    }

    if (max !== undefined && max !== null && max !== "") {
      return `Up to ${formatValue(max)}`;
    }

    return "None";
  };

  const formatList = (value) => {
    if (!Array.isArray(value) || value.length === 0) return "None";
    return value.map((item) => toPrettyLabel(item)).join(", ");
  };

  return {
    Location:
      safeFilters.city !== undefined && safeFilters.city !== null && safeFilters.city !== ""
        ? String(safeFilters.city)
        : "None",
    "Price Range": formatRange({
      exactKey: "price",
      minKey: "price_min",
      maxKey: "price_max",
      isPrice: true,
    }),
    Bedrooms: formatRange({
      exactKey: "bedrooms",
      minKey: "bedrooms_min",
      maxKey: "bedrooms_max",
    }),
    Bathrooms: formatRange({
      exactKey: "bathrooms",
      minKey: "bathrooms_min",
      maxKey: "bathrooms_max",
    }),
    Amenities: formatList(safeFilters.amenities),
    "Excluded Amenities": formatList(safeFilters.excluded_amenities),
  };
};

const extractBackendSignalChips = (signalData) => {
  if (!signalData || typeof signalData !== "object" || Array.isArray(signalData)) {
    return [];
  }

  const chips = [];

  const addValue = (key, value) => {
    if (value === null || value === undefined || value === "" || value === false) return;

    const label = toPrettyLabel(key);

    if (Array.isArray(value)) {
      value.forEach((item) => {
        if (item !== null && item !== undefined && item !== "") {
          chips.push(`${label}: ${toPrettyLabel(item)}`);
        }
      });
      return;
    }

    if (typeof value === "object") {
      Object.entries(value).forEach(([nestedKey, nestedValue]) => {
        addValue(nestedKey, nestedValue);
      });
      return;
    }

    if (value === true) {
      chips.push(label);
      return;
    }

    const displayValue = /price/i.test(key)
      ? formatPrice(value)
      : typeof value === "string"
        ? toPrettyLabel(value)
        : String(value);

    chips.push(`${label}: ${displayValue}`);
  };

  Object.entries(signalData).forEach(([key, value]) => {
    if (key === "listing_id") return;
    addValue(key, value);
  });

  return [...new Set(chips)].slice(0, 16);
};

const formatIssue = (issue) => {
  if (typeof issue === "string") return issue;
  if (!issue || typeof issue !== "object") return String(issue);
  if (issue.message) return issue.message;

  const category = issue.category ? toPrettyLabel(issue.category) : "";
  const pattern = issue.pattern ? `: ${issue.pattern}` : "";
  return `${category}${pattern}` || JSON.stringify(issue);
};

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const QUERY_FIELD_ICONS = {
  Location: "pin",
  "Price Range": "tag",
  Bedrooms: "bed",
  Bathrooms: "bath",
  Amenities: "sparkle",
  "Excluded Amenities": "shield",
};

function App() {
  const [query, setQuery] = useState("");
  const [numResults, setNumResults] = useState(5);
  const [useBm25, setUseBm25] = useState(false);
  const [sortOrder, setSortOrder] = useState("relevance");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [warning, setWarning] = useState("");
  const [error, setError] = useState("");
  const [hasSearched, setHasSearched] = useState(false);
  const [queryParsing, setQueryParsing] = useState(null);
  const [queryIntent, setQueryIntent] = useState(null);
  const [queryParsingError, setQueryParsingError] = useState("");
  const [queryIntentError, setQueryIntentError] = useState("");

  const requestJson = async (url, options) => {
    const response = await fetch(url, options);
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || `Request failed with status ${response.status}`);
    }

    return data;
  };

  const complianceFailed = (data) => {
    if (data?.compliant === false) return true;
    if (data?.is_compliant === false) return true;
    if (data?.passed === false) return true;
    if (data?.flagged === true) return true;
    if (Array.isArray(data?.violations) && data.violations.length > 0) return true;
    if (Array.isArray(data?.issues) && data.issues.length > 0) return true;
    return false;
  };

  const getComplianceWarning = (data) => {
    if (typeof data?.warning === "string" && data.warning.trim()) return data.warning;
    if (typeof data?.message === "string" && data.message.trim()) return data.message;
    if (Array.isArray(data?.violations) && data.violations.length > 0) {
      return `Compliance warning: ${data.violations.map(formatIssue).join(", ")}`;
    }
    if (Array.isArray(data?.issues) && data.issues.length > 0) {
      return `Compliance warning: ${data.issues.map(formatIssue).join(", ")}`;
    }
    return "This query did not pass the compliance check.";
  };

  const getRemarks = (listing) =>
    listing?.L_Remarks || listing?.remarks || listing?.Remarks || "";

  const handleSearch = async () => {
    const trimmedQuery = query.trim();
    const safeNumResults = Math.min(20, Math.max(1, Number(numResults) || 5));

    if (!trimmedQuery) {
      setWarning("");
      setResults([]);
      setQueryParsing(null);
      setQueryIntent(null);
      setQueryParsingError("");
      setQueryIntentError("");
      setHasSearched(false);
      setError("Please enter a search query first.");
      return;
    }

    setNumResults(safeNumResults);
    setLoading(true);
    setWarning("");
    setError("");
    setResults([]);
    setHasSearched(true);
    setQueryParsing(null);
    setQueryIntent(null);
    setQueryParsingError("");
    setQueryIntentError("");

    try {
      // Checkpoint 1: use your backend compliance checker.
      const complianceData = await requestJson(`${API_BASE_URL}/check-compliance`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: trimmedQuery }),
      });

      console.log("Compliance result:", complianceData);

      if (complianceFailed(complianceData)) {
        setWarning(getComplianceWarning(complianceData));
        return;
      }

      // Checkpoint 2: use your backend QueryParser.
      try {
        const parseData = await requestJson(`${API_BASE_URL}/parse-query`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: trimmedQuery }),
        });

        console.log("Query parsing result:", parseData);
        setQueryParsing(buildQueryParsingDisplay(parseData?.filters));
      } catch (parseError) {
        console.error("Query parsing failed:", parseError);
        setQueryParsing(null);
        setQueryParsingError(parseError.message || "Query parsing unavailable.");
      }

      // Checkpoint 3: use your backend intent classifier.
      try {
        const intentData = await requestJson(`${API_BASE_URL}/classify-intent`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: trimmedQuery }),
        });

        console.log("Intent result:", intentData);
        setQueryIntent({
          intent: intentData?.intent ?? "",
          confidence: intentData?.confidence ?? null,
        });
      } catch (intentError) {
        console.error("Intent classification failed:", intentError);
        setQueryIntent(null);
        setQueryIntentError(intentError.message || "Intent classification unavailable.");
      }

      // Checkpoint 4: keep the same search request/response contract,
      // but switch between semantic search and BM25 keyword search.
      const searchEndpoint = useBm25 ? "/bm25-search" : "/search";
      const searchData = await requestJson(`${API_BASE_URL}${searchEndpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: trimmedQuery, top_k: safeNumResults }),
      });

      console.log(`${useBm25 ? "BM25" : "Semantic"} search result:`, searchData);

      const listings = Array.isArray(searchData?.results) ? searchData.results : [];
      const enrichedResults = [];

      // Checkpoint 5: for each returned listing, use the backend signal extractor
      // and backend summarizer. A short delay keeps requests under the backend's
      // 10 requests/second rate limit when many results are requested.
      for (let index = 0; index < listings.length; index += 1) {
        const listing = listings[index];
        const remarks = getRemarks(listing);
        const listingId = getFirstValue(listing, [
          "L_ListingID",
          "listing_id",
          "ListingID",
          "id",
        ]);

        if (!remarks) {
          enrichedResults.push({
            ...listing,
            summary: "No listing remarks were available to summarize.",
            backendSignals: null,
          });
          continue;
        }

        const summaryRequest = requestJson(`${API_BASE_URL}/summarize`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ remarks, num_sentences: 3 }),
        });

        const signalRequest = requestJson(`${API_BASE_URL}/extract-signals`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            L_ListingID:
              listingId === "" || listingId === null || listingId === undefined
                ? null
                : String(listingId),
            L_Remarks: remarks,
          }),
        });

        const [summaryResult, signalResult] = await Promise.allSettled([
          summaryRequest,
          signalRequest,
        ]);

        if (summaryResult.status === "rejected") {
          console.error("Summary failed for listing:", summaryResult.reason);
        }

        if (signalResult.status === "rejected") {
          console.error("Signal extraction failed for listing:", signalResult.reason);
        }

        enrichedResults.push({
          ...listing,
          summary:
            summaryResult.status === "fulfilled"
              ? summaryResult.value?.summary || "Summary unavailable."
              : "Summary unavailable.",
          backendSignals:
            signalResult.status === "fulfilled" ? signalResult.value : null,
        });

        if (index < listings.length - 1) {
          await sleep(125);
        }
      }

      setResults(enrichedResults);
    } catch (searchError) {
      console.error("Search workflow failed:", searchError);
      setError(
        searchError.message || "Something went wrong while processing the search."
      );
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (event) => {
    if (event.key === "Enter" && !loading) handleSearch();
  };

  const parsingEntries = useMemo(
    () => (queryParsing ? Object.entries(queryParsing) : []),
    [queryParsing]
  );

  const sortedResults = useMemo(() => {
    if (sortOrder === "relevance") return results;

    const getNumericPrice = (listing) => {
      const rawPrice = getFirstValue(listing, [
        "price",
        "L_SystemPrice",
        "L_ListPrice",
        "list_price",
        "ListPrice",
      ]);

      if (rawPrice === "" || rawPrice === null || rawPrice === undefined) {
        return null;
      }

      const numericPrice = Number(String(rawPrice).replace(/[$,]/g, ""));
      return Number.isFinite(numericPrice) ? numericPrice : null;
    };

    return results
      .map((listing, originalIndex) => ({
        listing,
        originalIndex,
        price: getNumericPrice(listing),
      }))
      .sort((a, b) => {
        if (a.price === null && b.price === null) {
          return a.originalIndex - b.originalIndex;
        }
        if (a.price === null) return 1;
        if (b.price === null) return -1;

        const comparison =
          sortOrder === "price-asc" ? a.price - b.price : b.price - a.price;

        return comparison || a.originalIndex - b.originalIndex;
      })
      .map(({ listing }) => listing);
  }, [results, sortOrder]);

  return (
    <main className="app-shell">
      <aside className="search-sidebar">
        <div className="sidebar-glow sidebar-glow-one" />
        <div className="sidebar-glow sidebar-glow-two" />

        <div className="brand-block">
          <div>
            <h1>California<br />Real Estate Intelligent Search</h1>
            <p>Smarter Search. Brighter Homes.</p>
          </div>
        </div>

        <section className="search-panel">
          <div className="panel-heading">
            <div className="panel-icon"><Icon name="search" size={21} /></div>
            <div>
              <h2>Search Properties</h2>
              <p>Use natural language to find the right property.</p>
            </div>
          </div>

          <label htmlFor="search-query">What are you looking for?</label>
          <div className="input-with-icon">
            <input
              id="search-query"
              className="sidebar-input"
              type="text"
              placeholder="e.g. houses with beach view"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={handleKeyDown}
            />
            <Icon name="search" size={18} />
          </div>

          <label htmlFor="result-count">Number of results</label>
          <input
            id="result-count"
            className="sidebar-input result-count-input"
            type="number"
            min="1"
            max="20"
            step="1"
            value={numResults}
            onChange={(event) => setNumResults(event.target.value)}
            onKeyDown={handleKeyDown}
          />

          <div className="search-mode-row">
            <div className="search-mode-copy">
              <span className="search-mode-title">BM25 Keyword Search</span>
              <span className="search-mode-description">
                {useBm25 ? "Using keyword ranking" : "Using semantic ranking"}
              </span>
            </div>
            <button
              type="button"
              className={`search-mode-switch ${useBm25 ? "active" : ""}`}
              role="switch"
              aria-checked={useBm25}
              aria-label="Toggle BM25 keyword search"
              onClick={() => setUseBm25((current) => !current)}
              disabled={loading}
            >
              <span className="search-mode-knob" />
            </button>
          </div>

          <button className="search-button" onClick={handleSearch} disabled={loading}>
            {loading ? (
              <>
                <span className="button-spinner" /> Searching...
              </>
            ) : (
              <>
                <Icon name="search" size={19} /> Search
              </>
            )}
          </button>
        </section>

        <div className="sidebar-benefits">
          <div className="benefit-row">
            <span className="benefit-icon"><Icon name="home" /></span>
            <div><strong>Find your perfect property</strong><span>Homes, condos, land and more</span></div>
          </div>
          <div className="benefit-row">
            <span className="benefit-icon"><Icon name="sparkle" /></span>
            <div><strong>Natural-language search</strong><span>Search listings using everyday property terms</span></div>
          </div>
          <div className="benefit-row">
            <span className="benefit-icon"><Icon name="shield" /></span>
            <div><strong>Real, up-to-date listings</strong><span>Built from trusted listing data</span></div>
          </div>
          <div className="benefit-row">
            <span className="benefit-icon"><Icon name="heart" /></span>
            <div><strong>Turn searches into addresses</strong><span>Search simply. Compare quickly.</span></div>
          </div>
        </div>

      </aside>

      <section className="results-pane">
        <header className="results-header">
          <p className="eyebrow">PROPERTY DISCOVERY</p>
          <h2>Search Results</h2>
          <p>Understand the query first, then review the most relevant properties.</p>
        </header>

        <div className="insight-grid">
          <section className="insight-card parsing-card">
            <div className="insight-title-row">
              <span className="insight-icon blue"><Icon name="document" /></span>
              <div>
                <h3>Query Parsing Results</h3>
                <p>Extracted information from your search query</p>
              </div>
            </div>

            {!hasSearched ? (
              <div className="empty-insight">
                Enter a search on the left to see how the query is parsed.
              </div>
            ) : parsingEntries.length ? (
              <div className="parsing-grid">
                {parsingEntries.map(([label, value], index) => {
                  const isMissing = value === "None";

                  return (
                    <div className="parsing-item" key={`${label}-${index}`}>
                      <span className="parsing-field-icon" aria-hidden="true">
                        <Icon name={QUERY_FIELD_ICONS[label] || "sparkle"} size={19} />
                      </span>
                      <span className="parsing-label">{label}</span>
                      <span className={`parsing-value ${isMissing ? "muted" : ""}`}>
                        {isMissing ? "Not specified" : value}
                      </span>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="empty-insight">
                {queryParsingError || "Your backend parser did not return any structured filters for this query."}
              </div>
            )}
          </section>

          <section className="insight-card intent-card">
            <div className="insight-title-row">
              <span className="insight-icon orange"><Icon name="target" /></span>
              <div>
                <h3>Query Intent</h3>
                <p>What the search is trying to accomplish</p>
              </div>
            </div>

            {!hasSearched ? (
              <div className="empty-insight">
                The detected query intent will appear here after a search.
              </div>
            ) : queryIntent ? (
              <div className="intent-result">
                <span className="intent-house"><Icon name="home" size={25} /></span>
                <div>
                  <span className="intent-kicker">Detected intent</span>
                  <strong>{queryIntent.intent ? toPrettyLabel(queryIntent.intent) : "No intent returned"}</strong>
                  <p>
                    {typeof queryIntent.confidence === "number"
                      ? `Backend confidence: ${(queryIntent.confidence * 100).toFixed(1)}%`
                      : "No confidence score was returned by the backend."}
                  </p>
                </div>
              </div>
            ) : (
              <div className="empty-insight">
                {queryIntentError || "Intent classification was unavailable for this query."}
              </div>
            )}
          </section>
        </div>

        {warning && <div className="status-message warning-message">{warning}</div>}
        {error && <div className="status-message error-message">{error}</div>}

        <div className="results-title-row">
          <div>
            <span className="results-count">
              {loading ? "Searching properties..." : hasSearched ? `${results.length} Results Found` : "Property Results"}
            </span>
            <span className="results-caption">
              {hasSearched && !loading
                ? sortOrder === "relevance"
                  ? useBm25
                    ? "Ranked by BM25 keyword relevance"
                    : "Ranked by semantic similarity"
                  : sortOrder === "price-asc"
                    ? "Sorted by price from low to high"
                    : "Sorted by price from high to low"
                : "Your matching listings will appear below"}
            </span>
          </div>
          {hasSearched && !loading && (
            <div className="results-controls">
              <div className="sort-control">
                <label htmlFor="sort-order">Sort by</label>
                <select
                  id="sort-order"
                  value={sortOrder}
                  onChange={(event) => setSortOrder(event.target.value)}
                >
                  <option value="relevance">Relevance</option>
                  <option value="price-asc">Price: Low to High</option>
                  <option value="price-desc">Price: High to Low</option>
                </select>
              </div>

              <div className="result-meta-chips">
                <span className={`search-mode-badge ${useBm25 ? "bm25" : "semantic"}`}>
                  {useBm25 ? "BM25" : "Semantic"}
                </span>
                <span className="result-limit-chip">Top {Number(numResults) || 5}</span>
              </div>
            </div>
          )}
        </div>

        <div className="results-list">
          {loading && (
            <>
              <div className="result-card skeleton-card"><div className="skeleton-line wide" /><div className="skeleton-line medium" /><div className="skeleton-chip-row"><span /><span /><span /><span /></div><div className="skeleton-line full" /><div className="skeleton-line full" /><div className="skeleton-line short" /></div>
              <div className="result-card skeleton-card"><div className="skeleton-line wide" /><div className="skeleton-line medium" /><div className="skeleton-chip-row"><span /><span /><span /></div><div className="skeleton-line full" /><div className="skeleton-line full" /></div>
            </>
          )}

          {!loading && hasSearched && !warning && !error && results.length === 0 && (
            <div className="no-results-card">
              <span><Icon name="search" size={24} /></span>
              <h3>No matching listings found</h3>
              <p>Try making the search a little broader or increasing the number of results.</p>
            </div>
          )}

          {!loading &&
            sortedResults.map((result, index) => {
              const listingId = getFirstValue(result, ["L_ListingID", "listing_id", "ListingID", "id"]);
              const address = getFirstValue(result, ["L_Address", "address", "Address", "street_address"]);
              const city = getFirstValue(result, ["L_City", "city", "City"]);
              const state = getFirstValue(result, ["L_State", "state", "State"]);
              const price = getFirstValue(result, ["price", "L_ListPrice", "list_price", "ListPrice"]);
              const beds = getFirstValue(result, ["beds", "bedrooms", "L_Bedrooms", "Bedrooms"]);
              const baths = getFirstValue(result, ["baths", "bathrooms", "L_Bathrooms", "Bathrooms"]);
              const propertyType = getFirstValue(result, ["property_type", "PropertyType", "L_PropertyType", "type"]);
              const remarks = getRemarks(result);
              const signals = extractBackendSignalChips(result.backendSignals);
              const fullLocation = [address, city, state].filter(Boolean).join(", ");

              return (
                <article className="result-card" key={listingId || index}>
                  <div className="listing-header">
                    <div>
                      <div className="listing-title-row">
                        <h3>Listing {index + 1}</h3>
                        {listingId && <span className="listing-id">ID {listingId}</span>}
                      </div>
                      {fullLocation && (
                        <div className="listing-location">
                          <Icon name="pin" size={16} />
                          <span>{fullLocation}</span>
                        </div>
                      )}
                    </div>
                    {price && <div className="listing-price">{formatPrice(price)}</div>}
                  </div>

                  {(beds || baths || propertyType) && (
                    <div className="listing-facts">
                      {beds && <span><Icon name="bed" size={17} /> {beds} {Number(beds) === 1 ? "Bedroom" : "Bedrooms"}</span>}
                      {baths && <span><Icon name="bath" size={17} /> {baths} {Number(baths) === 1 ? "Bathroom" : "Bathrooms"}</span>}
                      {propertyType && <span><Icon name="home" size={17} /> {toPrettyLabel(propertyType)}</span>}
                    </div>
                  )}

                  <div className="signal-section">
                    <div className="signal-heading"><Icon name="sparkle" size={17} /> Property Signal Extractor</div>
                    <div className="signal-chips">
                      {signals.length ? signals.map((signal, signalIndex) => (
                        <span className={`signal-chip chip-${signalIndex % 5}`} key={`${signal}-${signalIndex}`}>{signal}</span>
                      )) : <span className="signal-chip chip-muted">No strong property signals detected</span>}
                    </div>
                  </div>

                  <div className="summary-section">
                    <h4>Summary</h4>
                    <p>{result.summary || "Summary unavailable."}</p>
                  </div>

                  <details className="remark-details">
                    <summary>
                      <span className="remark-summary-label"><Icon name="document" size={16} /> View original listing remark</span>
                      <Icon name="chevron" size={18} />
                    </summary>
                    <div className="original-remark">
                      {remarks || "No original listing remark is available for this property."}
                    </div>
                  </details>
                </article>
              );
            })}
        </div>
      </section>
    </main>
  );
}

export default App;
