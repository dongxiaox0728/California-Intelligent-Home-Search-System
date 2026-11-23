import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import brandIcon from "./assets/ca-home-search-icon.png";
import homeBackground from "./assets/california-coast-at-dusk.jpg";
import SearchCriteria from "./SearchCriteria.jsx";
import "./App.css";

const API_BASE_URL = import.meta.env.DEV
  ? "http://localhost:8000"
  : "/api";
const SOURCE_REPOSITORY_URL = "https://github.com/dongxiaox0728/IDX-nlp";

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
    chevron: <path d="m6 9 6 6 6-6" />,
    check: <path d="m5 12 4 4L19 6" />,
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

const requestJson = async (url, options) => {
  const response = await fetch(url, options);
  const data = await response.json();

  options.signal.throwIfAborted();

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

const normalizeLimit = (value) => Math.min(20, Math.max(1, Math.trunc(Number(value) || 5)));

const readRefinements = (params) => {
  try {
    const value = JSON.parse(params.get("filters"));
    return value && typeof value === "object" && !Array.isArray(value) ? value : undefined;
  } catch {
    return undefined;
  }
};

const readSearchFromUrl = () => {
  if (window.location.pathname !== "/results") return null;
  const params = new URLSearchParams(window.location.search);
  const query = params.get("q")?.trim();
  if (!query) return null;
  const useBm25 = params.get("mode") === "bm25";
  return {
    query,
    limit: normalizeLimit(params.get("limit")),
    useBm25,
    refinements: useBm25 ? undefined : readRefinements(params),
  };
};

function SearchModePicker({ useBm25, onChange }) {
  const [open, setOpen] = useState(false);
  const picker = useRef(null);
  const trigger = useRef(null);
  const label = useBm25 ? "Keyword search" : "Smart search";

  useEffect(() => {
    if (!open) return;
    const closeOnOutsideClick = (event) => {
      if (!picker.current?.contains(event.target)) setOpen(false);
    };
    document.addEventListener("pointerdown", closeOnOutsideClick);
    return () => document.removeEventListener("pointerdown", closeOnOutsideClick);
  }, [open]);

  const close = () => {
    setOpen(false);
    trigger.current?.focus();
  };

  return (
    <div
      className="search-mode-picker"
      ref={picker}
      onBlur={(event) => {
        if (event.relatedTarget && !event.currentTarget.contains(event.relatedTarget)) setOpen(false);
      }}
      onKeyDown={(event) => {
        if (open && event.key === "Escape") {
          event.preventDefault();
          close();
        }
      }}
    >
      <button
        type="button"
        className="search-mode-trigger"
        ref={trigger}
        aria-expanded={open}
        aria-controls="search-mode-options"
        aria-label={`Search mode: ${label}`}
        onClick={() => setOpen(!open)}
      >
        <span>{useBm25 ? "Keyword" : "Smart"}<span className="search-mode-suffix"> search</span></span>
        <Icon name="chevron" size={15} />
      </button>
      <div id="search-mode-options" className="search-mode-options" role="group" aria-label="Search mode" hidden={!open}>
        {[false, true].map((option) => (
          <button
            key={String(option)}
            type="button"
            aria-pressed={useBm25 === option}
            onClick={() => {
              onChange(option);
              close();
            }}
          >
            {option ? "Keyword search (BM25)" : "Smart search"}
            {useBm25 === option && <Icon name="check" size={17} />}
          </button>
        ))}
      </div>
    </div>
  );
}

function App() {
  const [submittedSearch, setSubmittedSearch] = useState(readSearchFromUrl);
  const [query, setQuery] = useState(submittedSearch?.query ?? "");
  const [numResults, setNumResults] = useState(submittedSearch?.limit ?? 5);
  const [useBm25, setUseBm25] = useState(submittedSearch?.useBm25 ?? false);
  const [sortOrder, setSortOrder] = useState("relevance");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(Boolean(submittedSearch));
  const [warning, setWarning] = useState("");
  const [error, setError] = useState("");
  const [queryParsing, setQueryParsing] = useState(null);
  const [queryIntent, setQueryIntent] = useState(null);
  const [queryParsingError, setQueryParsingError] = useState("");
  const [queryIntentError, setQueryIntentError] = useState("");
  const [searchOptions, setSearchOptions] = useState(null);
  const [cityStatus, setCityStatus] = useState("Loading cities…");
  const resultsHeading = useRef(null);
  const isResultsPage = Boolean(submittedSearch);

  const openSearch = useCallback((search) => {
    setQuery(search?.query ?? "");
    setNumResults(search?.limit ?? 5);
    setUseBm25(search?.useBm25 ?? false);
    setWarning("");
    setError("");
    setResults([]);
    setQueryParsing(null);
    setQueryIntent(null);
    setQueryParsingError("");
    setQueryIntentError("");
    setLoading(Boolean(search));
    setSubmittedSearch(search);
  }, []);

  useEffect(() => {
    const onPopState = () => openSearch(readSearchFromUrl());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, [openSearch]);

  useEffect(() => {
    if (isResultsPage) resultsHeading.current?.focus({ preventScroll: true });
  }, [isResultsPage]);

  useEffect(() => {
    if (!isResultsPage || useBm25 || searchOptions) return;

    const controller = new AbortController();
    requestJson(`${API_BASE_URL}/search-options`, { signal: controller.signal })
      .then((options) => {
        setSearchOptions(options);
        setCityStatus("");
      })
      .catch(() => {
        if (!controller.signal.aborted) setCityStatus("City options are temporarily unavailable.");
      });
    return () => controller.abort();
  }, [isResultsPage, useBm25, searchOptions]);

  const submitSearch = (search) => {
    const params = new URLSearchParams({ q: search.query });
    if (search.limit !== 5) params.set("limit", String(search.limit));
    if (search.useBm25) params.set("mode", "bm25");
    if (search.refinements) params.set("filters", JSON.stringify(search.refinements));
    const url = `/results?${params}`;
    if (url !== window.location.pathname + window.location.search) {
      window.history.pushState(null, "", url);
    }
    openSearch(search);
  };

  const handleSearch = (event) => {
    event.preventDefault();
    const trimmedQuery = query.trim();
    if (loading || !trimmedQuery) return;

    const limit = normalizeLimit(numResults);
    const refinements = trimmedQuery === submittedSearch?.query ? submittedSearch.refinements : undefined;
    submitSearch({ query: trimmedQuery, limit, useBm25, refinements });
    window.scrollTo(0, 0);
  };

  const applyCriteria = (edits) => {
    const refinements = { ...submittedSearch.refinements };
    for (const [field, value] of Object.entries(edits)) {
      refinements[field] = field === "city" ? value : { ...refinements[field], ...value };
    }
    submitSearch({ ...submittedSearch, refinements });
    window.scrollTo(0, 0);
  };

  useEffect(() => {
    if (!submittedSearch) return;

    const controller = new AbortController();
    const { signal } = controller;
    const { query: trimmedQuery, limit, useBm25, refinements } = submittedSearch;
    const queryBody = { query: trimmedQuery, refinements };

    const runSearch = async () => {
      await Promise.resolve();
      if (signal.aborted) return;

      try {
        const complianceData = await requestJson(`${API_BASE_URL}/check-compliance`, {
          method: "POST",
          signal,
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: trimmedQuery }),
        });

        console.log("Compliance result:", complianceData);

        if (complianceFailed(complianceData)) {
          setWarning(getComplianceWarning(complianceData));
          return;
        }

        try {
          const parseData = await requestJson(`${API_BASE_URL}/parse-query`, {
            method: "POST",
            signal,
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(queryBody),
          });

          console.log("Query parsing result:", parseData);
          setQueryParsing(parseData);
        } catch (parseError) {
          if (signal.aborted) return;
          console.error("Query parsing failed:", parseError);
          setQueryParsing(null);
          setQueryParsingError(parseError.message || "Query parsing unavailable.");
        }

        try {
          const intentData = await requestJson(`${API_BASE_URL}/classify-intent`, {
            method: "POST",
            signal,
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query: trimmedQuery }),
          });

          console.log("Intent result:", intentData);
          setQueryIntent({
            intent: intentData?.intent ?? "",
            confidence: intentData?.confidence ?? null,
          });
        } catch (intentError) {
          if (signal.aborted) return;
          console.error("Intent classification failed:", intentError);
          setQueryIntent(null);
          setQueryIntentError(intentError.message || "Intent classification unavailable.");
        }

        const searchEndpoint = useBm25 ? "/bm25-search" : "/search";
        const searchData = await requestJson(`${API_BASE_URL}${searchEndpoint}`, {
          method: "POST",
          signal,
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ...queryBody, top_k: limit }),
        });

        console.log("Property search result:", searchData);

        const listings = Array.isArray(searchData?.results) ? searchData.results : [];
        const enrichedResults = [];

        for (let index = 0; index < listings.length; index += 1) {
          if (signal.aborted) return;
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
            signal,
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ remarks, num_sentences: 3 }),
          });

          const signalRequest = requestJson(`${API_BASE_URL}/extract-signals`, {
            method: "POST",
            signal,
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
          if (signal.aborted) return;

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
        if (signal.aborted) return;
        console.error("Search workflow failed:", searchError);
        setError(
          searchError.message || "Something went wrong while processing the search."
        );
      } finally {
        if (!signal.aborted) setLoading(false);
      }
    };

    void runSearch();
    return () => controller.abort();
  }, [submittedSearch]);

  const parsingEntries = useMemo(
    () => (queryParsing ? Object.entries(buildQueryParsingDisplay(queryParsing.filters)) : []),
    [queryParsing]
  );

  const showCriteria = ([label, value]) => (
    <div className="parsing-item" key={label}>
      <span className="parsing-field-icon" aria-hidden="true">
        <Icon name={QUERY_FIELD_ICONS[label] || "sparkle"} size={19} />
      </span>
      <span className="parsing-label">{label}</span>
      <span className={`parsing-value ${value === "None" ? "muted" : ""}`}>
        {value === "None" ? "Not specified" : value}
      </span>
    </div>
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

  const brand = (
    <a className="site-brand" href="/">
      <img src={brandIcon} alt="" width="38" height="38" />
      <span>CA Home Search</span>
    </a>
  );

  const sourceLink = (
    <a
      className="source-link"
      href={SOURCE_REPOSITORY_URL}
      target="_blank"
      rel="noopener noreferrer"
      aria-label="View source on GitHub (opens in a new tab)"
      title="View source on GitHub"
    >
      <svg className="icon" width="23" height="23" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
        <path d="M8 0C3.58 0 0 3.58 0 8a8 8 0 0 0 5.47 7.59c.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.55 7.55 0 0 1 2-.27c.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8 8 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
      </svg>
    </a>
  );

  const searchForm = (
    <form id="property-search" className="property-search" role="search" onSubmit={handleSearch}>
      <Icon name="search" size={23} />
      <input
        type="search"
        name="q"
        aria-label="Describe the home you’re looking for"
        placeholder="Try “A home in Malibu with an ocean view”"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        required
      />
      {!isResultsPage && <SearchModePicker useBm25={useBm25} onChange={setUseBm25} />}
      <button type="submit" disabled={loading || !query.trim()}>
        {loading ? "Searching…" : "Search"}
      </button>
    </form>
  );

  if (!submittedSearch) {
    return (
      <main className="home-page" style={{ "--home-background": `url(${homeBackground})` }}>
        <header className="home-header">
          {brand}
          {sourceLink}
        </header>
        <div className="home-content">
          <h1>Find your dream property in California</h1>
          {searchForm}
        </div>
      </main>
    );
  }

  return (
    <div className="results-page">
      <header className="results-topbar">
        <div className="results-topbar-inner">
          {brand}
          {searchForm}
          {sourceLink}
        </div>
      </header>

      <main className="results-layout">
        <aside className="search-context" aria-label="About your search">
          <section className="insight-card">
            <div className="insight-title-row">
              <span className="insight-icon"><Icon name="document" /></span>
              <h2>Search Criteria</h2>
            </div>

            {queryParsing && !useBm25 && !loading ? (
              <SearchCriteria parsed={queryParsing} options={searchOptions} cityStatus={cityStatus} onApply={applyCriteria}>
                {parsingEntries.slice(-2).map(showCriteria)}
                {queryParsing.semantic_words && (
                  <div className="criteria-description">
                    <span className="criteria-label">From your search</span>
                    <span>{queryParsing.semantic_words}</span>
                  </div>
                )}
              </SearchCriteria>
            ) : parsingEntries.length ? (
              <div className="parsing-grid">
                {parsingEntries.map(showCriteria)}
                {useBm25 && <p className="criteria-help">Use Smart search to edit these criteria.</p>}
              </div>
            ) : (
              <div className="empty-insight" role="status">
                {queryParsingError || (loading
                  ? "Reading your search criteria…"
                  : "We couldn’t find any specific criteria in your search.")}
              </div>
            )}
          </section>

          <section className="insight-card">
            <div className="insight-title-row">
              <span className="insight-icon"><Icon name="target" /></span>
              <h2>Search Goal</h2>
            </div>

            {queryIntent ? (
              <div className="intent-result">
                <span className="intent-house"><Icon name="home" size={25} /></span>
                <div>
                  <span className="intent-kicker">Suggested goal</span>
                  <strong>{queryIntent.intent ? toPrettyLabel(queryIntent.intent) : "Search goal unavailable"}</strong>
                  {typeof queryIntent.confidence === "number" && (
                    <p>{(queryIntent.confidence * 100).toFixed(1)}% confidence</p>
                  )}
                </div>
              </div>
            ) : (
              <div className="empty-insight" role="status">
                {queryIntentError || (loading
                  ? "Identifying what you’re looking for…"
                  : "We couldn’t determine a goal for this search.")}
              </div>
            )}
          </section>
        </aside>

        <section className="results-pane" aria-labelledby="property-results-title">
          <div className="results-title-row">
            <div>
              <h1 id="property-results-title" ref={resultsHeading} tabIndex={-1}>Property Results</h1>
              <p className="results-caption" role="status">
                {loading ? "Searching properties…" : warning || error ? "" : `${results.length} ${results.length === 1 ? "home" : "homes"} found`}
                {submittedSearch.useBm25 && !warning && !error && " · BM25 keyword search"}
              </p>
            </div>
            <div className="results-controls">
              <label className="search-limit">
                Search limit
                <input
                  type="number"
                  form="property-search"
                  min="1"
                  max="20"
                  step="1"
                  value={numResults}
                  onChange={(event) => setNumResults(event.target.value)}
                  disabled={loading}
                />
              </label>
              {!loading && results.length > 0 && (
                <label className="sort-control">
                  Sort by
                  <select value={sortOrder} onChange={(event) => setSortOrder(event.target.value)}>
                    <option value="relevance">Best match</option>
                    <option value="price-asc">Price: Low to High</option>
                    <option value="price-desc">Price: High to Low</option>
                  </select>
                </label>
              )}
            </div>
          </div>

          {warning && <div className="status-message warning-message" role="alert">{warning}</div>}
          {error && <div className="status-message error-message" role="alert">{error}</div>}

          <div className="results-list">
            {loading && (
              <div className="results-list" aria-hidden="true">
                <div className="result-card skeleton-card"><div className="skeleton-line wide" /><div className="skeleton-line medium" /><div className="skeleton-chip-row"><span /><span /><span /><span /></div><div className="skeleton-line full" /><div className="skeleton-line full" /><div className="skeleton-line short" /></div>
                <div className="result-card skeleton-card"><div className="skeleton-line wide" /><div className="skeleton-line medium" /><div className="skeleton-chip-row"><span /><span /><span /></div><div className="skeleton-line full" /><div className="skeleton-line full" /></div>
              </div>
            )}

            {!loading && !warning && !error && results.length === 0 && (
              <div className="no-results-card">
                <span><Icon name="search" size={24} /></span>
                <h3>No matching listings found</h3>
                <p>Try removing a feature or searching in a broader area.</p>
              </div>
            )}

            {!loading &&
              sortedResults.map((result, index) => {
                const listingId = getFirstValue(result, ["L_ListingID", "listing_id", "ListingID", "id"]);
                const address = String(getFirstValue(result, ["L_Address", "address", "Address", "street_address"])).trim();
                const city = getFirstValue(result, ["L_City", "city", "City"]);
                const state = getFirstValue(result, ["L_State", "state", "State"]);
                const price = getFirstValue(result, ["price", "L_ListPrice", "list_price", "ListPrice"]);
                const beds = getFirstValue(result, ["beds", "bedrooms", "L_Bedrooms", "Bedrooms"]);
                const baths = getFirstValue(result, ["baths", "bathrooms", "L_Bathrooms", "Bathrooms"]);
                const propertyType = getFirstValue(result, ["property_type", "PropertyType", "L_PropertyType", "type"]);
                const remarks = getRemarks(result);
                const signals = extractBackendSignalChips(result.backendSignals);
                const locality = [city, state].filter(Boolean).join(", ");
                const listingTitle = address
                  ? [address, locality].filter(Boolean).join(", ")
                  : `Listing ${index + 1}`;

                return (
                  <article className="result-card" key={listingId || index}>
                    <div className="listing-header">
                      <div>
                        <div className="listing-title-row">
                          <h3>{listingTitle}</h3>
                          {listingId && <span className="listing-id">ID {listingId}</span>}
                        </div>
                        {!address && locality && (
                          <div className="listing-location">
                            <Icon name="pin" size={16} />
                            <span>{locality}</span>
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
    </div>
  );
}

export default App;
