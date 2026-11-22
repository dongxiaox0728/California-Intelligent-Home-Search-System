import { useRef, useState } from "react";

const fields = [
  { name: "price", label: "Price range", preferredLabel: "Preferred price", ceiling: 100_000_000, fallbackMax: 5_000_000, step: 1 },
  { name: "bedrooms", label: "Bedrooms", preferredLabel: "Preferred bedrooms", ceiling: 20, fallbackMax: 10, step: 1 },
  { name: "bathrooms", label: "Bathrooms", preferredLabel: "Preferred bathrooms", ceiling: 20, fallbackMax: 10, step: 0.5 },
];

const dollars = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

const inputValue = (value) => value == null ? "" : String(value);
const numericValue = (value) => value === "" ? null : Number(value);

function initialValues(parsed) {
  const conditions = parsed.filters ?? {};
  const rules = parsed.structured_filters?.ranking_rules ?? [];
  const ranges = fields.map(({ name }) => {
    const preferred = rules.find((rule) => rule.field === name && rule.direction === "closest");
    return [name, {
      min: inputValue(conditions[`${name}_min`] ?? conditions[name]),
      max: inputValue(conditions[`${name}_max`] ?? conditions[name]),
      preferred: inputValue(preferred?.target),
    }];
  });
  return { city: conditions.city ?? "", ...Object.fromEntries(ranges) };
}

function CityPicker({ city, cities, cityStatus, onChange }) {
  const details = useRef(null);
  const summary = useRef(null);
  const searchInput = useRef(null);
  const [query, setQuery] = useState("");
  const matchingCities = cities.filter((name) => name.toLowerCase().includes(query.trim().toLowerCase()));

  const close = () => {
    details.current.open = false;
    summary.current.focus();
  };

  const select = (value) => {
    onChange(value);
    close();
  };

  return (
    <div className="criteria-city">
      <span className="criteria-label" id="criteria-location-label">Location</span>
      <details
        className="criteria-city-picker"
        ref={details}
        onToggle={(event) => {
          if (event.currentTarget.open) searchInput.current.focus();
          else setQuery("");
        }}
        onBlur={(event) => {
          if (event.relatedTarget && !event.currentTarget.contains(event.relatedTarget)) {
            event.currentTarget.open = false;
          }
        }}
        onKeyDown={(event) => {
          if (event.key === "Escape" && details.current.open) {
            event.preventDefault();
            close();
          }
          if (event.key === "Enter" && event.target === searchInput.current) {
            event.preventDefault();
            const match = matchingCities.find((name) => name.toLowerCase() === query.trim().toLowerCase());
            if (match || matchingCities.length === 1) select(match ?? matchingCities[0]);
          }
        }}
      >
        <summary ref={summary} aria-labelledby="criteria-location-label criteria-city-value">
          <span id="criteria-city-value">{city || "Any city"}</span>
        </summary>
        <div className="criteria-city-menu">
          <input
            ref={searchInput}
            type="search"
            aria-label="Search cities"
            placeholder="Search cities"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <div className="criteria-city-list">
            <button type="button" aria-pressed={!city} onClick={() => select("")}>Any city</button>
            {matchingCities.map((name) => (
              <button type="button" key={name} aria-pressed={city === name} onClick={() => select(name)}>{name}</button>
            ))}
            {matchingCities.length === 0 && (
              <p role="status">{cityStatus || "No matching cities."}</p>
            )}
          </div>
        </div>
      </details>
    </div>
  );
}

function RangeFilter({ field, values, datasetMax, onChange }) {
  const { name, label, preferredLabel, fallbackMax, ceiling, step } = field;
  const isPrice = name === "price";
  const largestValue = Math.max(1, datasetMax ?? fallbackMax, Number(values.max), Number(values.min));
  const maximum = Math.min(ceiling, Math.ceil(largestValue / step) * step);
  const rangeEnd = isPrice ? 100 : maximum;
  const priceScale = Math.log1p(maximum / 100_000);
  const position = (value) => isPrice ? (100 * Math.log1p(value / 100_000)) / priceScale : value;
  const low = position(Math.max(0, Number(values.min)));
  const high = position(values.max === "" ? maximum : Math.min(maximum, Number(values.max)));
  const format = (value) => isPrice ? dollars.format(value) : String(value);

  const move = (bound, value) => {
    const edge = bound === "min" ? 0 : rangeEnd;
    if (value === edge) {
      onChange(bound, "");
      return;
    }
    const amount = isPrice ? 5_000 * Math.round(20 * Math.expm1((value / 100) * priceScale)) : value;
    const opposite = numericValue(values[bound === "min" ? "max" : "min"]);
    const constrained = bound === "min" ? Math.min(amount, opposite ?? maximum) : Math.max(amount, opposite ?? 0);
    onChange(bound, String(Math.min(maximum, constrained)));
  };

  return (
    <fieldset className="criteria-range">
      <legend className="criteria-label">{label}</legend>
      <div className="criteria-slider" style={{ "--range-start": `${(low / rangeEnd) * 100}%`, "--range-end": `${(high / rangeEnd) * 100}%` }}>
        <input
          type="range" min="0" max={rangeEnd} step={isPrice ? 1 : step}
          value={low} aria-label={`${label} minimum slider`}
          aria-valuetext={values.min === "" ? "Any minimum" : format(values.min)}
          onChange={(event) => move("min", Number(event.target.value))}
        />
        <input
          type="range" min="0" max={rangeEnd} step={isPrice ? 1 : step}
          value={high} aria-label={`${label} maximum slider`}
          aria-valuetext={values.max === "" ? "Any maximum" : format(values.max)}
          onChange={(event) => move("max", Number(event.target.value))}
        />
      </div>
      <div className={`criteria-range-inputs${isPrice ? " criteria-price-inputs" : ""}`}>
        {[["min", "Min"], ["max", "Max"], ["preferred", "Preferred"]].map(([key, caption]) => (
          <label key={key}>
            {caption}{isPrice ? " ($)" : ""}
            <input
              type="number" min="0" max={ceiling} step={name === "bedrooms" ? "1" : "any"}
              inputMode={name === "bedrooms" ? "numeric" : "decimal"}
              aria-label={key === "preferred" ? preferredLabel : `${label} ${key === "min" ? "minimum" : "maximum"}`}
              placeholder={key === "preferred" ? "Optional" : "Any"}
              value={values[key]}
              onChange={(event) => onChange(key, event.target.value)}
            />
          </label>
        ))}
      </div>
    </fieldset>
  );
}

export default function SearchCriteria({ parsed, options, cityStatus, onApply, children }) {
  const [initial] = useState(() => initialValues(parsed));
  const [draft, setDraft] = useState(initial);
  const [validationError, setValidationError] = useState("");
  const changed = draft.city !== initial.city || fields.some(({ name }) => (
    Object.keys(draft[name]).some((key) => numericValue(draft[name][key]) !== numericValue(initial[name][key]))
  ));

  const submit = (event) => {
    event.preventDefault();
    if (!changed) return;
    const edits = {};
    if (draft.city !== initial.city) edits.city = draft.city || null;
    for (const { name, label } of fields) {
      const { min, max, preferred } = draft[name];
      const low = numericValue(min);
      const high = numericValue(max);
      if (low !== null && high !== null && low > high) {
        setValidationError(`${label}: the minimum must be at or below the maximum.`);
        return;
      }
      const rangeEdits = {};
      if (low !== numericValue(initial[name].min) || high !== numericValue(initial[name].max)) {
        Object.assign(rangeEdits, { min: low, max: high });
      }
      const target = numericValue(preferred);
      if (target !== numericValue(initial[name].preferred)) rangeEdits.preferred = target;
      if (Object.keys(rangeEdits).length) edits[name] = rangeEdits;
    }
    onApply(edits);
  };

  return (
    <form className="criteria-form" onSubmit={submit}>
      <CityPicker
        city={draft.city}
        cities={options?.cities ?? []}
        cityStatus={cityStatus}
        onChange={(city) => setDraft((current) => ({ ...current, city }))}
      />
      {fields.map((field) => (
        <RangeFilter
          key={field.name}
          field={field}
          values={draft[field.name]}
          datasetMax={options?.maxima?.[field.name]}
          onChange={(key, value) => {
            setValidationError("");
            setDraft((current) => ({ ...current, [field.name]: { ...current[field.name], [key]: value } }));
          }}
        />
      ))}
      {children}
      {validationError && <p className="criteria-help" role="alert">{validationError}</p>}
      <button className="criteria-apply" type="submit" disabled={!changed}>Apply filters</button>
    </form>
  );
}
