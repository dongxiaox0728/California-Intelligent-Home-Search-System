"""
    Coordinate parsing, hard filtering and four ranking paths.

    SearchOrchestrator().search(query) returns up to 100 listings plus diagnostics.
    Semantic components load only when needed. Structured-only/newest searches use
    all eligible database rows, even those without embeddings. ListingContractDate is the default first-listing date field for newest-first
    searches. Override with LISTING_DATE_COLUMN or date_column if needed.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, timezone
import os

from scripts.structured_ranker import StructuredRanker
from scripts.weighted_ranker import WeightedRanker


class SearchOrchestrator:
    def __init__(self, parser=None, hard_filter=None, semantic_searcher=None, date_column=None):
        # Imports/initialization are deferred to avoid loading a model for numeric searches.
        self.parser = parser
        self.hard_filter = hard_filter
        self.semantic_searcher = semantic_searcher
        self.date_column = date_column
        self.structured_ranker = StructuredRanker()

    def _searcher(self):
        if self.semantic_searcher is None:
            from scripts.semantic_searcher import SemanticSearcher
            self.semantic_searcher = SemanticSearcher()
        if self.semantic_searcher.metadata is None:
            self.semantic_searcher.load()
        return self.semantic_searcher

    @staticmethod
    def _unique_rows(rows):
        unique = {}
        for source in rows:
            if not isinstance(source, Mapping):
                raise TypeError('Hard filter must return listing dictionaries.')
            row = dict(source)
            value = row.get('L_ListingID')
            if value is None or isinstance(value, bool) or not str(value).strip():
                raise ValueError('An eligible listing has no valid L_ListingID.')
            listing_id = str(value).strip()
            row['L_ListingID'] = listing_id
            if listing_id in unique and unique[listing_id] != row:
                raise ValueError('Conflicting eligible rows share a listing ID.')
            unique[listing_id] = row
        # Stable tie order independent of database row order.
        return [unique[key] for key in sorted(unique)]

    @staticmethod
    def _date(value):
        if value is None:
            return None
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
            except ValueError:
                return None
        if isinstance(value, datetime):
            try:
                return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None
                        else value.astimezone(timezone.utc))
            except (ValueError, OverflowError):
                return None
        if isinstance(value, date):
            return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
        return None

    @staticmethod
    def _single_signal(row, mode):
        row = dict(row)
        if mode == 'structured':
            row.update(final_score=row['structured_score'], similarity_score=None,
                       semantic_rank=None, semantic_weight=0.0, structured_weight=1.0)
        elif mode == 'semantic':
            row.update(final_score=row['similarity_score'], semantic_rank=row['rank'],
                       structured_score=None, structured_rank=None, rule_scores=[],
                       semantic_weight=1.0, structured_weight=0.0)
        else:
            row.update(final_score=None, similarity_score=None, structured_score=None,
                       semantic_rank=None, structured_rank=None, rule_scores=[],
                       semantic_weight=0.0, structured_weight=0.0)
        return row

    """
        Return a report with parsed_query, mode, coverage counts and results.
        Limits apply after ranking. Up to 100 can be requested; the interactive
        test requests 10. Dates with missing/invalid values go last; equal dates
        break ties by listing ID. Ranking ties are stable (combined uses index order;
        single-signal paths use listing ID). Naive dates are treated
        as UTC for ordering. If every date is invalid, fail rather than pretend
        that an arbitrary order is newest-first.
    """
    def search(self, query: str, top_k: int = 100, *, parsed_query=None):

        if not isinstance(query, str) or not query.strip():
            raise ValueError('query must be a nonempty string.')
        if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 100:
            raise ValueError('top_k must be an integer from 1 to 100.')
        if self.hard_filter is None:
            from scripts.hard_constraints_filter import HardConstraintsFilter
            self.hard_filter = HardConstraintsFilter()
        if parsed_query is None:
            if self.parser is None:
                from scripts.query_parser import QueryParser
                self.parser = QueryParser()
            parsed_query = self.parser.parse(query)
        parsed = parsed_query
        if not isinstance(parsed, Mapping) or not isinstance(parsed.get('semantic_words'), str):
            raise ValueError('Parser must return semantic_words and structured_filters.')
        rules = self.structured_ranker._rules(parsed)
        semantic_text = parsed['semantic_words'].strip()
        mode = ('combined' if rules else 'semantic') if semantic_text else ('structured' if rules else 'newest')
        rows = self._unique_rows(self.hard_filter.filter(parsed))
        report = dict(parsed_query=parsed, mode=mode, requested_count=top_k,
                      eligible_count=len(rows), candidate_count=len(rows),
                      missing_index_count=0, invalid_date_count=0, date_column=None,
                      warnings=[], results=[])
        if not rows:
            return report

        if mode in ('combined', 'semantic'):
            searcher = self._searcher()
            indexed = set(searcher.metadata['L_ListingID'].astype(str).str.strip())
            candidates = [row for row in rows if row['L_ListingID'] in indexed]
            report['candidate_count'] = len(candidates)
            report['missing_index_count'] = len(rows) - len(candidates)
            if report['missing_index_count']:
                report['warnings'].append(
                    f"{report['missing_index_count']} eligible listings have no indexed embedding; "
                    'semantic search covers only the indexed dataset snapshot.')
            if not candidates:
                return report
            if mode == 'combined':
                ranked = WeightedRanker(searcher).rank(candidates, parsed)[:top_k]
                # WeightedRanker scores all candidates before its top-100 cutoff.
            else:
                semantic = searcher.search_eligible(
                    query=semantic_text, eligible_ids=[row['L_ListingID'] for row in candidates],
                    top_k=len(candidates))
                by_id = {row['L_ListingID']: row for row in candidates}
                ranked = []
                for result in semantic:
                    row = dict(result)
                    row.update(by_id[str(result['L_ListingID']).strip()])
                    # Restore scoring fields after merging database attributes.
                    row.update(similarity_score=result['similarity_score'], rank=result['rank'])
                    ranked.append(self._single_signal(row, 'semantic'))
                ranked.sort(key=lambda row: row['L_ListingID'])
                ranked.sort(key=lambda row: row['final_score'], reverse=True)
                ranked = ranked[:top_k]
        elif mode == 'structured':
            ranked = [self._single_signal(row, mode) for row in
                      self.structured_ranker.rank(rows, rules, top_k=top_k)]
        else:
            column = self.date_column or os.getenv('LISTING_DATE_COLUMN') or 'ListingContractDate'
            if not any(column in row for row in rows):
                raise ValueError(f'Listing date column {column!r} is absent from the database results.')
            dates = {row['L_ListingID']: self._date(row.get(column)) for row in rows}
            invalid = sum(value is None for value in dates.values())
            if invalid == len(rows):
                raise ValueError(f'No valid dates in {column!r}; cannot order by newest listing.')
            report.update(date_column=column, invalid_date_count=invalid)
            if invalid:
                report['warnings'].append(f'{invalid} listings have missing/invalid dates and are ordered last.')
            floor = datetime.min.replace(tzinfo=timezone.utc)
            rows.sort(key=lambda row: dates[row['L_ListingID']] or floor, reverse=True)
            ranked = [self._single_signal(row, mode) for row in rows[:top_k]]
        for rank, row in enumerate(ranked, 1):
            row['rank'] = rank
        report['results'] = ranked
        return report
