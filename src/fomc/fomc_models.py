from typing import List, Dict, Optional, Literal
from pydantic import BaseModel, Field
from datetime import date


class PolicyRegime(BaseModel):
    """Current Fed policy regime classification"""
    current: str = Field(
        description="Current policy regime based on communication analysis"
    )
    conviction: str = Field(
        description="High Confidence (0.8-1.0), Medium Confidence (0.5-0.79), Low Confidence (0.0-0.49) with communication-based evidence"
    )
    expected_duration: str = Field(
        description="Estimated regime duration based on Fed guidance and economic conditions"
    )
    triggers: List[str] = Field(
        description="Specific data points or conditions that would shift regime"
    )


class MandatePriorities(BaseModel):
    """Fed mandate priority assessment"""
    inflation_focus: str = Field(
        description="Based on statement evolution"
    )
    employment_focus: str = Field(
        description="Based on guidance changes"
    )
    financial_stability: str = Field(
        description="Based on communication frequency"
    )
    dual_mandate_balance: str = Field(
        description="Based on Fed emphasis"
    )


class FedAssessment(BaseModel):
    """Overall Fed assessment and guidance"""
    mandate_priorities: MandatePriorities
    policy_guidance: List[str] = Field(
        description="Directional insights for institutional positioning"
    )
    asymmetric_opportunities: List[str] = Field(
        description="Fed communication based risk/reward setups"
    )
    institutional_considerations: str = Field(
        description="Policy transmission insights for professional participants"
    )


class MonitoringPriority(BaseModel):
    """Data points the Fed is monitoring"""
    data_point: str = Field(description="Specific economic indicator Fed is watching")
    next_release: date = Field(description="Next data release date in YYYY-MM-DD")
    importance: Literal["high", "medium", "low"] = Field(
        description="high, medium, low with market impact score"
    )
    potential_impact: str = Field(
        description="Fed reaction function sensitivity and asset class implications"
    )
    policy_thresholds: str = Field(
        description="Specific levels or trends that matter for Fed decisions"
    )


class ConfidenceAssessment(BaseModel):
    """Confidence in the analysis"""
    base_case: str = Field(
        description="Probability confidence based on Fed communication consistency"
    )
    policy_analysis: str = Field(
        description="Conviction level based on verified communication quality"
    )
    key_uncertainties: List[str] = Field(
        description="Major unknown factors with market impact potential"
    )
    data_limitations: List[str] = Field(
        description="Explicit acknowledgment of information gaps"
    )


class MeetingCycleSynthesis(BaseModel):
    """Synthesis of the entire meeting cycle"""
    policy_regime: PolicyRegime
    fed_assessment: FedAssessment
    monitoring_priorities: List[MonitoringPriority]
    confidence_assessment: ConfidenceAssessment


class BondsDirection(BaseModel):
    """Bond market directional impact from monetary policy"""
    yields_direction: str = Field(
        description="Direction with uncertainty range",
        alias="yields"
    )
    curve: str = Field(
        description="Based on Fed dot plot"
    )
    magnitude: Literal["high", "medium", "low"] = Field(
        description="high|medium|low based on historical Fed cycle parallels"
    )
    focus: List[str] = Field(
        description="Specific maturities or sectors most affected by monetary policy"
    )
    policy_transmission: str = Field(
        description="Policy rate expectations, term premium, and Fed balance sheet effects only"
    )


class EquitiesDirection(BaseModel):
    """Equity market directional impact from monetary policy"""
    direction: str = Field(
        description="From monetary policy impact"
    )
    magnitude: Literal["high", "medium", "low"] = Field(
        description="high|medium|low based on discount rate sensitivity to Fed policy"
    )
    sensitivity_focus: List[str] = Field(
        description="Sectors most sensitive to interest rate changes and credit conditions"
    )
    resistant_sectors: List[str] = Field(
        description="Sectors least sensitive to monetary policy transmission"
    )
    policy_transmission: str = Field(
        description="Discount rate mechanism, credit availability channel, and Fed liquidity effects only"
    )


class CurrenciesDirection(BaseModel):
    """Currency market directional impact from monetary policy"""
    usd: str = Field(
        description="Based on Fed policy vs other central banks"
    )
    carry_trades: str = Field(
        description="Based on Fed interest rate policy"
    )
    magnitude: Literal["high", "medium", "low"] = Field(
        description="high|medium|low based on monetary policy divergence with other central banks"
    )
    policy_transmission: str = Field(
        description="Interest rate differentials and Fed policy risk sentiment effects only"
    )


class CommoditiesDirection(BaseModel):
    """Commodity market directional impact from monetary policy"""
    direction: str = Field(
        description="From Fed monetary policy channels"
    )
    magnitude: Literal["high", "medium", "low"] = Field(
        description="high|medium|low based on real interest rate and USD monetary policy impact"
    )
    focus: List[str] = Field(
        description="Specific commodities most sensitive to Fed real rates and USD policy"
    )
    policy_transmission: str = Field(
        description="Real interest rates via Fed policy, USD strength from Fed actions, and monetary policy inflation expectations only"
    )


class AssetDirections(BaseModel):
    """Cross-asset directional impacts"""
    bonds: BondsDirection
    equities: EquitiesDirection
    currencies: CurrenciesDirection
    commodities: CommoditiesDirection


class BaseCase(BaseModel):
    """Base case scenario for Fed policy path"""
    scenario: str = Field(description="Most likely Fed policy path description")
    probability: str = Field(
        description="Estimated percentage with uncertainty range from communication analysis"
    )
    asset_directions: AssetDirections


class AlternativeScenario(BaseModel):
    """Alternative policy scenario"""
    name: str = Field(description="Descriptive Fed policy scenario name")
    description: str = Field(description="Specific outcome with data-dependent triggers")
    probability: str = Field(description="Estimated percentage from Fed guidance analysis")
    market_impact_score: str = Field(description="Composite risk score 0 to 10")
    asset_directions: AssetDirections


class CrossAssetImpact(BaseModel):
    """Cross-asset market impact analysis"""
    base_case: BaseCase
    alternative_scenarios: List[AlternativeScenario]


class KeySignal(BaseModel):
    """Individual Fed communication signal"""
    communication: str = Field(description="Specific Fed statement or guidance change")
    signal_date: date = Field(description="Signal date in YYYY-MM-DD")
    market_score: str = Field(description="0 to 10 with uncertainty range")
    direction_shift: str = Field(
        description="Change direction"
    )
    impact: str = Field(description="Market impact description using directional language")
    sources: List[str] = Field(
        description="Verified Fed communication sources with timestamps"
    )


class PolicyIndicators(BaseModel):
    """Policy stance indicators"""
    rate_guidance: str = Field(description="Forward guidance evolution and clarity")
    mandate_emphasis: str = Field(description="Inflation vs employment prioritization trends")
    tool_deployment: str = Field(
        description="Communication, rate, liquidity, or regulatory tool usage"
    )
    credibility_maintenance: str = Field(
        description="Consistency of Fed follow-through on guidance"
    )


class PolicyStanceCluster(BaseModel):
    """Policy stance communication cluster"""
    headline: str = Field(description="Descriptive summary of Fed policy direction")
    tone: str = Field(
        description="more hawkish, neutral, more dovish assessment"
    )
    consistency: Literal["high", "medium", "low"] = Field(
        description="high, medium, low across communication types"
    )
    avg_market_score: str = Field(description="Numerical average 0 to 10 with uncertainty range")
    market_impact: str = Field(description="Directional assessment")
    key_signals: List[KeySignal]
    policy_indicators: PolicyIndicators


class AssessmentIndicators(BaseModel):
    """Economic assessment indicators"""
    growth_outlook: str = Field(description="GDP and employment forecast evolution")
    inflation_expectations: str = Field(description="Price stability assessment and projections")
    financial_conditions: str = Field(description="Credit markets and asset valuation concerns")
    global_risks: str = Field(
        description="International spillover and coordination considerations"
    )


class EconomicAssessmentCluster(BaseModel):
    """Economic assessment communication cluster"""
    headline: str = Field(description="Descriptive summary of Fed economic outlook")
    tone: str = Field(
        description="more optimistic, neutral, more pessimistic assessment"
    )
    consistency: Literal["high", "medium", "low"] = Field(
        description="high, medium, low across forecasts and communications"
    )
    avg_market_score: str = Field(description="Numerical average 0 to 10 with uncertainty range")
    market_impact: str = Field(description="Directional assessment")
    key_signals: List[KeySignal]
    assessment_indicators: AssessmentIndicators


class TransmissionIndicators(BaseModel):
    """Market transmission indicators"""
    rate_transmission: str = Field(description="Policy rate to market rate pass-through")
    credit_channels: str = Field(description="Lending conditions and availability evolution")
    wealth_effects: str = Field(description="Asset price impact on consumption and investment")
    expectations_anchor: str = Field(
        description="Forward guidance effectiveness and credibility"
    )


class MarketTransmissionCluster(BaseModel):
    """Market transmission communication cluster"""
    headline: str = Field(description="Descriptive summary of Fed market impact mechanisms")
    tone: str = Field(
        description="effective, mixed, ineffective policy transmission assessment"
    )
    consistency: Literal["high", "medium", "low"] = Field(
        description="high, medium, low across asset classes"
    )
    avg_market_score: str = Field(description="Numerical average 0 to 10 with uncertainty range")
    market_impact: str = Field(description="Directional assessment")
    key_signals: List[KeySignal]
    transmission_indicators: TransmissionIndicators


class CommunicationClusters(BaseModel):
    """All communication clusters"""
    policy_stance: PolicyStanceCluster
    economic_assessment: EconomicAssessmentCluster
    market_transmission: MarketTransmissionCluster


class CycleStage(BaseModel):
    """Fed cycle stage assessment"""
    current_phase: str = Field(description="Early/mid/late stage of tightening or easing cycle")
    mandate_balance: str = Field(
        description="Inflation-focused, employment-focused, or balanced approach"
    )
    global_coordination: str = Field(
        description="Leading, following, or independent of other central banks"
    )
    credibility_status: str = Field(
        description="Based on guidance follow-through"
    )


class PolicyDynamics(BaseModel):
    """Fed policy dynamics"""
    internal_consensus: str = Field(
        description="FOMC agreement based on dissents and minutes"
    )
    external_pressure: str = Field(
        description="Political, market, or international constraints on policy"
    )
    tool_effectiveness: str = Field(
        description="Assessment of current policy tool impact on economy"
    )
    communication_clarity: str = Field(
        description="Guidance and forward direction"
    )


class EscalationIndicators(BaseModel):
    """Policy escalation indicators"""
    tool_progression: str = Field(
        description="Communication to rate to liquidity to regulatory tool sequence"
    )
    mandate_pressure: str = Field(
        description="Inflation, employment, or financial stability priority assessment"
    )
    threshold_levels: str = Field(
        description="Identified data points that trigger policy escalation"
    )
    stabilizing_factors: str = Field(
        description="Elements supporting current policy stance maintenance"
    )


class FedPositioning(BaseModel):
    """Fed positioning analysis"""
    cycle_stage: CycleStage
    policy_dynamics: PolicyDynamics
    escalation_indicators: EscalationIndicators


class GuidanceClarityIndicator(BaseModel):
    """Guidance clarity evolution indicator"""
    direction: str = Field(
        description="Evolution direction"
    )
    conviction: str = Field(description="High/Medium/Low Confidence")
    indicators: List[str] = Field(
        description="Specific indicators",
        default=["forward guidance specificity", "conditionality changes", "timeline precision"]
    )


class MandateEmphasisIndicator(BaseModel):
    """Mandate emphasis evolution indicator"""
    direction: str = Field(
        description="Evolution direction"
    )
    conviction: str = Field(description="High/Medium/Low Confidence")
    indicators: List[str] = Field(
        description="Specific indicators",
        default=["statement language", "SEP priorities", "speech themes"]
    )


class ToolReadinessIndicator(BaseModel):
    """Tool readiness evolution indicator"""
    direction: str = Field(
        description="Evolution direction"
    )
    conviction: str = Field(description="High/Medium/Low Confidence")
    indicators: List[str] = Field(
        description="Specific indicators",
        default=["facility preparation", "QE/QT pace", "regulatory coordination"]
    )


class GlobalAwarenessIndicator(BaseModel):
    """Global awareness evolution indicator"""
    direction: str = Field(
        description="Evolution direction"
    )
    conviction: str = Field(description="High/Medium/Low Confidence")
    indicators: List[str] = Field(
        description="Specific indicators",
        default=["international references", "spillover concerns", "G7 coordination"]
    )


class CommunicationEvolution(BaseModel):
    """Fed communication evolution tracking"""
    guidance_clarity: GuidanceClarityIndicator
    mandate_emphasis: MandateEmphasisIndicator
    tool_readiness: ToolReadinessIndicator
    global_awareness: GlobalAwarenessIndicator


class CredibilityIndicators(BaseModel):
    """Fed credibility indicators"""
    guidance_sequence: str = Field(
        description="Consistency between Fed projections and subsequent policy actions"
    )
    market_alignment: str = Field(
        description="Degree to which Fed communication moves markets in intended direction"
    )
    data_responsiveness: str = Field(
        description="Fed reaction function predictability based on economic data"
    )
    expected_persistence: str = Field(
        description="Likely duration of current communication approach and policy stance"
    )


class ConsistencyAssessment(BaseModel):
    """Fed communication consistency assessment"""
    specification: str = Field(
        default="Policy Credibility = β_guidance×Guidance_Follow_Through + β_forecasts×SEP_Accuracy + β_communication×Message_Consistency + ε",
        description="Policy Credibility = β_guidance×Guidance_Follow_Through + β_forecasts×SEP_Accuracy + β_communication×Message_Consistency + ε"
    )
    communication_evolution: CommunicationEvolution
    credibility_indicators: CredibilityIndicators


class FedCommunicationAnalysis(BaseModel):
    """Fed communication analysis"""
    consistency_assessment: ConsistencyAssessment


class AnalogousCycle(BaseModel):
    """Historical analogous Fed cycle"""
    period: str = Field(description="Historical Fed cycle description")
    similarities: List[str] = Field(description="Specific policy patterns matching current environment")
    differences: List[str] = Field(
        description="Key distinctions from current Fed communication approach"
    )
    outcomes: List[str] = Field(description="How policy evolved based on historical verification")
    lessons: List[str] = Field(
        description="Applicable insights for current Fed cycle positioning"
    )
    confidence: str = Field(
        description="High/Medium/Low Confidence of comparison based on verification quality"
    )


class PatternRecognition(BaseModel):
    """Historical pattern recognition"""
    fed_behavior: str = Field(
        description="Historical Fed communication and policy patterns from verified sources"
    )
    cycle_sequence: str = Field(
        description="Typical tool progression in similar economic environments"
    )
    market_response: str = Field(
        description="Historical market reaction to similar Fed communication evolution"
    )
    transmission_mechanisms: str = Field(
        description="How similar Fed cycles transmitted through asset classes"
    )


class HistoricalContext(BaseModel):
    """Historical context for current Fed cycle"""
    analogous_cycles: List[AnalogousCycle]
    pattern_recognition: PatternRecognition


class Timeframe(BaseModel):
    """Analysis timeframe"""
    meeting_cycle: date = Field(description="FOMC meeting date in YYYY-MM_DD")
    next_meeting: date = Field(description="Next FOMC meeting date in YYYY-MM_DD")
    key_data_releases: List[str] = Field(
        description="Critical economic data before next meeting"
    )
    update_frequency: str = Field(
        description="Post-meeting immediate, minutes release, inter-meeting speeches"
    )


class Methodology(BaseModel):
    """Analysis methodology"""
    impact_scoring: str = Field(description="L-V-I market impact scoring framework 0 to 10 scale")
    communication_analysis: str = Field(
        description="Cross-reference verification across all Fed communication types"
    )
    cycle_mapping: str = Field(
        description="Policy stance assessment using historical Fed cycle patterns"
    )
    cross_asset_transmission: str = Field(
        description="Directional impact analysis across bonds, equities, FX, commodities"
    )
    historical_validation: str = Field(
        description="Pattern recognition with Fed cycle verification"
    )


class DataLimitations(BaseModel):
    """Data limitations acknowledgment"""
    public_information: str = Field(
        description="Based on official Fed communications and verified market analysis"
    )
    real_time_events: str = Field(
        description="2-4 hour lag on Fed communication releases and initial market impact"
    )
    fed_intentions: str = Field(
        description="Inferred from communications and actions, actual FOMC deliberations private"
    )
    precision_disclaimer: str = Field(
        description="Directional trends emphasized over specific yield or price predictions"
    )


class AnalysisFramework(BaseModel):
    """Overall analysis framework"""
    timeframe: Timeframe
    methodology: Methodology
    data_limitations: DataLimitations


class FOMCAnalysisOutput(BaseModel):
    """Complete FOMC Communications Analysis Output"""
    meeting_cycle_synthesis: MeetingCycleSynthesis
    cross_asset_impact: CrossAssetImpact
    communication_clusters: CommunicationClusters
    fed_positioning: FedPositioning
    fed_communication_analysis: FedCommunicationAnalysis
    historical_context: HistoricalContext
    analysis_framework: AnalysisFramework