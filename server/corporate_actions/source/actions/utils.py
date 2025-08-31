from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from decimal import Decimal
import statistics
from collections import defaultdict


@dataclass
class FieldConfidence:
    """Confidence metrics for individual fields."""
    value: Any
    confidence_score: float  # 0.0 to 1.0
    source_count: int
    agreement_ratio: float  # Ratio of sources that agree on this value
    disagreement_details: List[str]


class ConfidenceCalculator:
    """Calculates confidence scores based on cross-source agreement."""

    def __init__(self, date_tolerance_days: int = 2, amount_tolerance_percent: float = 3.0):
        self.date_tolerance_days = date_tolerance_days
        self.amount_tolerance_percent = amount_tolerance_percent

    def calculate_field_confidence(self, field_name: str, values_by_source: Dict[str, Any],
                                   source_reliabilities: Dict[str, float]) -> FieldConfidence:
        """Calculate confidence for a specific field across sources."""

        if not values_by_source:
            return FieldConfidence(None, 0.0, 0, 0.0, [])

        # Filter out None values
        valid_values = {k: v for k, v in values_by_source.items() if v is not None}

        if not valid_values:
            return FieldConfidence(None, 0.0, 0, 0.0, [])

        if len(valid_values) == 1:
            source, value = next(iter(valid_values.items()))
            reliability = source_reliabilities.get(source, 0.5)
            return FieldConfidence(value, reliability, 1, 1.0, [])

        if field_name.endswith('_date'):
            return self._calculate_date_confidence(valid_values, source_reliabilities)
        elif field_name.endswith('_amount'):
            return self._calculate_amount_confidence(valid_values, source_reliabilities)
        else:
            return self._calculate_categorical_confidence(valid_values, source_reliabilities)

    def _calculate_date_confidence(self, values_by_source: Dict[str, str],
                                   source_reliabilities: Dict[str, float]) -> FieldConfidence:
        """Calculate confidence for date fields."""
        # Convert dates to datetime objects
        date_objects = {}
        for source, date_str in values_by_source.items():
            try:
                date_objects[source] = datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                continue

        if not date_objects:
            return FieldConfidence(None, 0.0, 0, 0.0, [])

        # Find clusters of similar dates
        date_clusters = self._cluster_dates(date_objects, self.date_tolerance_days)

        # Choose the cluster with highest total reliability
        best_cluster = max(date_clusters, key=lambda cluster:
        sum(source_reliabilities.get(source, 0.5) for source in cluster['sources']))

        # Calculate agreement ratio
        agreement_ratio = len(best_cluster['sources']) / len(date_objects)

        # Calculate confidence score
        base_confidence = sum(source_reliabilities.get(source, 0.5)
                              for source in best_cluster['sources']) / len(best_cluster['sources'])
        agreement_bonus = agreement_ratio * 0.3
        confidence = min(1.0, base_confidence + agreement_bonus)

        # Generate disagreement details
        disagreements = []
        if agreement_ratio < 1.0:
            for source, date_obj in date_objects.items():
                if source not in best_cluster['sources']:
                    disagreements.append(f"{source}: {date_obj.strftime('%Y-%m-%d')}")

        return FieldConfidence(
            value=best_cluster['representative_date'].strftime('%Y-%m-%d'),
            confidence_score=confidence,
            source_count=len(date_objects),
            agreement_ratio=agreement_ratio,
            disagreement_details=disagreements
        )

    def _calculate_amount_confidence(self, values_by_source: Dict[str, Decimal],
                                     source_reliabilities: Dict[str, float]) -> FieldConfidence:
        """Calculate confidence for monetary amount fields."""
        # Convert to float for comparison
        float_values = {source: float(amount) for source, amount in values_by_source.items()}

        # Find clusters of similar amounts
        amount_clusters = self._cluster_amounts(float_values, self.amount_tolerance_percent)

        # Choose the cluster with highest total reliability
        best_cluster = max(amount_clusters, key=lambda cluster:
        sum(source_reliabilities.get(source, 0.5) for source in cluster['sources']))

        # Calculate agreement ratio
        agreement_ratio = len(best_cluster['sources']) / len(float_values)

        # Calculate confidence score
        base_confidence = sum(source_reliabilities.get(source, 0.5)
                              for source in best_cluster['sources']) / len(best_cluster['sources'])
        agreement_bonus = agreement_ratio * 0.4
        confidence = min(1.0, base_confidence + agreement_bonus)

        # Generate disagreement details
        disagreements = []
        if agreement_ratio < 1.0:
            for source, amount in float_values.items():
                if source not in best_cluster['sources']:
                    disagreements.append(f"{source}: {amount}")

        # Return the most reliable source's original Decimal value from the best cluster
        best_source = max(best_cluster['sources'],
                          key=lambda s: source_reliabilities.get(s, 0.5))

        return FieldConfidence(
            value=values_by_source[best_source],
            confidence_score=confidence,
            source_count=len(float_values),
            agreement_ratio=agreement_ratio,
            disagreement_details=disagreements
        )

    def _calculate_categorical_confidence(self, values_by_source: Dict[str, Any],
                                          source_reliabilities: Dict[str, float]) -> FieldConfidence:
        """Calculate confidence for categorical fields."""
        # Count occurrences of each value, weighted by source reliability
        value_scores = defaultdict(float)
        value_sources = defaultdict(list)

        for source, value in values_by_source.items():
            reliability = source_reliabilities.get(source, 0.5)
            value_scores[value] += reliability
            value_sources[value].append(source)

        # Choose the value with highest total reliability score
        best_value = max(value_scores.keys(), key=lambda v: value_scores[v])

        # Calculate agreement ratio
        agreement_ratio = len(value_sources[best_value]) / len(values_by_source)

        # Calculate confidence
        base_confidence = value_scores[best_value] / len(value_sources[best_value])
        agreement_bonus = agreement_ratio * 0.3
        confidence = min(1.0, base_confidence + agreement_bonus)

        # Generate disagreement details
        disagreements = []
        if agreement_ratio < 1.0:
            for value, sources in value_sources.items():
                if value != best_value:
                    disagreements.append(f"{', '.join(sources)}: {value}")

        return FieldConfidence(
            value=best_value,
            confidence_score=confidence,
            source_count=len(values_by_source),
            agreement_ratio=agreement_ratio,
            disagreement_details=disagreements
        )

    def _cluster_dates(self, date_objects: Dict[str, datetime], tolerance_days: int) -> List[Dict]:
        """Cluster dates that are within tolerance of each other."""
        clusters = []
        remaining_dates = date_objects.copy()

        while remaining_dates:
            anchor_source, anchor_date = next(iter(remaining_dates.items()))
            cluster_sources = [anchor_source]
            del remaining_dates[anchor_source]

            to_remove = []
            for source, date_obj in remaining_dates.items():
                if abs((date_obj - anchor_date).days) <= tolerance_days:
                    cluster_sources.append(source)
                    to_remove.append(source)

            for source in to_remove:
                del remaining_dates[source]

            cluster_dates = [date_objects[source] for source in cluster_sources]
            cluster_dates.sort()
            representative_date = cluster_dates[len(cluster_dates) // 2]

            clusters.append({
                'sources': cluster_sources,
                'representative_date': representative_date
            })

        return clusters

    def _cluster_amounts(self, float_values: Dict[str, float], tolerance_percent: float) -> List[Dict]:
        """Cluster amounts that are within percentage tolerance of each other."""
        clusters = []
        remaining_amounts = float_values.copy()

        while remaining_amounts:
            anchor_source, anchor_amount = next(iter(remaining_amounts.items()))
            cluster_sources = [anchor_source]
            del remaining_amounts[anchor_source]

            to_remove = []
            for source, amount in remaining_amounts.items():
                if anchor_amount == 0:
                    if amount == 0:
                        cluster_sources.append(source)
                        to_remove.append(source)
                else:
                    percent_diff = abs(amount - anchor_amount) / anchor_amount * 100
                    if percent_diff <= tolerance_percent:
                        cluster_sources.append(source)
                        to_remove.append(source)

            for source in to_remove:
                del remaining_amounts[source]

            clusters.append({
                'sources': cluster_sources,
                'representative_amount': anchor_amount
            })

        return clusters

    def calculate_overall_confidence(self, field_confidences: Dict[str, FieldConfidence],
                                     field_weights: Dict[str, float]) -> float:
        """Calculate overall confidence score with field weights."""
        if not field_confidences:
            return 0.0

        weighted_sum = 0.0
        total_weight = 0.0

        for field_name, confidence in field_confidences.items():
            weight = field_weights.get(field_name, 0.01)
            weighted_sum += confidence.confidence_score * weight
            total_weight += weight

        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def calculate_source_agreement_score(self, field_confidences: Dict[str, FieldConfidence]) -> float:
        """Calculate how well sources agree overall."""
        if not field_confidences:
            return 0.0

        agreement_ratios = [conf.agreement_ratio for conf in field_confidences.values()]
        return statistics.mean(agreement_ratios)