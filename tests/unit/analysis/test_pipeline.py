from minilucene.analysis import KeywordAnalyzer, StandardAnalyzer, Token
from minilucene.analysis.pipeline import Analyzer, LowercaseFilter
from minilucene.analysis.standard import KeywordTokenizer


def test_standard_analysis_preserves_offsets_and_stopword_gap():
    analyzer = StandardAnalyzer(stopwords=frozenset({"and"}))
    assert analyzer.analyze("Kafka AND Replicas") == (
        Token("kafka", 0, 0, 5),
        Token("replicas", 2, 10, 18),
    )


def test_keyword_analyzer_emits_whole_value():
    assert KeywordAnalyzer().analyze("Jonah Smith") == (
        Token("Jonah Smith", 0, 0, 11),
    )


def test_keyword_analyzer_emits_no_token_for_empty_value():
    assert KeywordAnalyzer().analyze("") == ()


def test_pipeline_applies_filters_in_order_without_changing_offsets():
    analyzer = Analyzer(KeywordTokenizer(), (LowercaseFilter(),))
    assert analyzer.analyze("MiXeD") == (Token("mixed", 0, 0, 5),)


def test_unicode_words_keep_original_character_offsets():
    assert StandardAnalyzer().analyze("你好 Kafka") == (
        Token("你好", 0, 0, 2),
        Token("kafka", 1, 3, 8),
    )
