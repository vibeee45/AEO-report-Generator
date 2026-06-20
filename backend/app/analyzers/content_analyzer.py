"""
Content Analyzer for AEO Report Generator
Analyzes BeautifulSoup objects for AEO (Answer Engine Optimization) signals.
"""

import re
import json
from bs4 import BeautifulSoup, Tag

from app.utils.logger import logger


def analyze_content(soup: BeautifulSoup) -> dict:
    """
    Analyze a BeautifulSoup object for AEO signals.
    
    Args:
        soup: BeautifulSoup object of the page to analyze
        
    Returns:
        Dictionary containing AEO analysis results
    """
    try:
        faq_present = _detect_faq_section(soup)
        faq_schema_present = _detect_faq_schema(soup)
        question_headings = _count_question_headings(soup)
        word_count = _count_words(soup)
        conversational_score = _count_conversational_words(soup)
        featured_snippet_score = _count_featured_snippet_elements(soup)
        content_score, breakdown = _calculate_content_score(
            
            faq_present=faq_present,
            faq_schema_present=faq_schema_present,
            question_headings=question_headings,
            word_count=word_count,
            conversational_score=conversational_score,
            featured_snippet_score=featured_snippet_score
        )
        
        return {
    "faq_present": faq_present,
    "faq_schema_present": faq_schema_present,
    "question_headings": question_headings,
    "word_count": word_count,
    "conversational_score": conversational_score,
    "featured_snippet_score": featured_snippet_score,
    "content_score": content_score,
    "content_breakdown": breakdown
}
        
    except Exception as e:

        logger.error(
        f"Content analysis failed: {e}",
        exc_info=True)

        return {
        "faq_present": False,
        "faq_schema_present": False,
        "question_headings": 0,
        "word_count": 0,
        "conversational_score": 0,
        "featured_snippet_score": 0,
        "content_score": 0,
        "content_breakdown": {
        "faq": 0,
        "questions": 0,
        "word_count": 0,
        "conversation": 0,
        "snippets": 0}
    }
        


def _detect_faq_section(soup: BeautifulSoup) -> bool:
    """
    Detect if a FAQ section is present on the page.
    
    Args:
        soup: BeautifulSoup object
        
    Returns:
        True if FAQ section detected, False otherwise
    """
    try:
        faq_patterns = [
            r'\bfaq\b',
            r'frequently\s+asked\s+questions?',
            r'common\s+questions?',
            r'questions?\s+and\s+answers?',
            r'\bq\s*&\s*a\b',
            r'\bq\s*and\s*a\b'
        ]
        
        # Check headings (h1-h6) for FAQ keywords
        for heading_tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            heading_text = heading_tag.get_text(strip=True).lower()
            for pattern in faq_patterns:
                if re.search(pattern, heading_text, re.IGNORECASE):
                    return True
        
        # Check for elements with FAQ-related IDs or classes
        faq_id_class_patterns = [r'\bfaq\b', r'frequently.asked', r'questions.answers']
        
        for element in soup.find_all(True):
            element_id = element.get('id', '')
            element_classes = ' '.join(element.get('class', []))
            combined = f"{element_id} {element_classes}".lower()
            
            for pattern in faq_id_class_patterns:
                if re.search(pattern, combined, re.IGNORECASE):
                    return True
        
        # Check for FAQ-like structure: multiple dt/dd pairs or question-answer patterns
        definition_lists = soup.find_all('dl')
        for dl in definition_lists:
            dt_tags = dl.find_all('dt')
            dd_tags = dl.find_all('dd')
            if len(dt_tags) >= 2 and len(dd_tags) >= 2:
                # Check if DT tags look like questions
                question_count = sum(
                    1 for dt in dt_tags 
                    if dt.get_text(strip=True).endswith('?')
                )
                if question_count >= 2:
                    return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error detecting FAQ section: {e}", exc_info=True)
        return False


def _detect_faq_schema(soup: BeautifulSoup) -> bool:
    """
    Detect if FAQ schema markup is present on the page.

    Args:
        soup: BeautifulSoup object

    Returns:
        True if FAQ schema detected, False otherwise
    """

    try:

        script_tags = soup.find_all(
            "script",
            type="application/ld+json"
        )

        for script in script_tags:

            if not script.string:
                continue

            try:

                schema_data = json.loads(
                    script.string
                )

                schemas = (
                    schema_data
                    if isinstance(schema_data, list)
                    else [schema_data]
                )

                for schema in schemas:

                    if _is_faq_schema(schema):
                        return True

            except (
                json.JSONDecodeError,
                AttributeError
            ):

                if "FAQPage" in (
                    script.string or ""
                ):
                    return True

        faq_microdata = soup.find(
            attrs={
                "itemtype":
                re.compile(
                    r"schema\.org/FAQPage",
                    re.IGNORECASE
                )
            }
        )

        if faq_microdata:
            return True

        faq_rdfa = soup.find(
            attrs={
                "typeof":
                re.compile(
                    r"FAQPage",
                    re.IGNORECASE
                )
            }
        )

        if faq_rdfa:
            return True

        return False

    except Exception as e:

        logger.error(
            f"Error detecting FAQ schema: {e}",
            exc_info=True
        )

        return False


def _is_faq_schema(schema: dict) -> bool:
    """
    Check if a schema dictionary represents an FAQ schema.
    
    Args:
        schema: Dictionary containing schema data
        
    Returns:
        True if FAQ schema, False otherwise
    """
    if not isinstance(schema, dict):
        return False
    
    schema_type = schema.get('@type', '')
    
    # Handle both string and list types
    if isinstance(schema_type, list):
        if any('FAQPage' in t for t in schema_type):
            return True
    elif 'FAQPage' in str(schema_type):
        return True
    
    # Check @graph for nested schemas
    graph = schema.get('@graph', [])
    if isinstance(graph, list):
        for item in graph:
            if _is_faq_schema(item):
                return True
    
    return False


def _count_question_headings(soup: BeautifulSoup) -> int:
    """
    Count headings that are question-based.
    
    Args:
        soup: BeautifulSoup object
        
    Returns:
        Count of question-based headings
    """
    try:
        question_word_pattern = re.compile(
            r'^\s*(what|why|how|when|where|which)\b',
            re.IGNORECASE
        )
        
        question_count = 0
        
        for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            heading_text = heading.get_text(strip=True)
            
            if not heading_text:
                continue
            
            # Check if heading ends with '?'
            if heading_text.endswith('?'):
                question_count += 1
                continue
            
            # Check if heading starts with question words
            if question_word_pattern.match(heading_text):
                question_count += 1
        
        return question_count
        
    except Exception as e:
        logger.error(f"Error counting question headings: {e}", exc_info=True)
        return 0


def _count_words(soup: BeautifulSoup) -> int:
    """
    Count total words in the page content.
    
    Args:
        soup: BeautifulSoup object
        
    Returns:
        Total word count
    """
    try:
        # Remove script and style tags to get clean text
        soup_copy = BeautifulSoup(str(soup), 'html.parser')
        
        for tag in soup_copy.find_all(['script', 'style', 'meta', 'link', 'noscript']):
            tag.decompose()
        
        text = soup_copy.get_text(separator=' ', strip=True)
        
        # Split on whitespace and filter out empty strings and non-word tokens
        words = [
            word for word in re.split(r'\s+', text)
            if word and re.search(r'[a-zA-Z0-9]', word)
        ]
        
        return len(words)
        
    except Exception as e:
        logger.error(f"Error counting words: {e}", exc_info=True)
        return 0


def _count_conversational_words(soup: BeautifulSoup) -> int:
    """
    Count occurrences of conversational words: you, your, we, our.
    
    Args:
        soup: BeautifulSoup object
        
    Returns:
        Total count of conversational word occurrences
    """
    try:
        # Remove script and style tags
        soup_copy = BeautifulSoup(str(soup), 'html.parser')
        
        for tag in soup_copy.find_all(['script', 'style', 'meta', 'link', 'noscript']):
            tag.decompose()
        
        text = soup_copy.get_text(separator=' ', strip=True)
        
        # Match whole words only
        conversational_pattern = re.compile(
            r'\b(you|your|we|our)\b',
            re.IGNORECASE
        )
        
        matches = conversational_pattern.findall(text)
        return len(matches)
        
    except Exception as e:
        logger.error(f"Error counting conversational words: {e}", exc_info=True)
        return 0


def _count_featured_snippet_elements(soup: BeautifulSoup) -> int:
    """
    Count elements that provide featured snippet opportunities.
    
    Args:
        soup: BeautifulSoup object
        
    Returns:
        Total count of featured snippet opportunity elements
    """
    try:
        count = 0
        
        # Count ordered lists
        ordered_lists = soup.find_all('ol')
        count += len(ordered_lists)
        
        # Count unordered lists
        unordered_lists = soup.find_all('ul')
        count += len(unordered_lists)
        
        # Count tables
        tables = soup.find_all('table')
        count += len(tables)
        
        return count
        
    except Exception as e:
        logger.error(f"Error counting featured snippet elements: {e}", exc_info=True)
        return 0


def _calculate_content_score(
    faq_present: bool,
    faq_schema_present: bool,
    question_headings: int,
    word_count: int,
    conversational_score: int,
    featured_snippet_score: int
) -> int:
    """
    Calculate an overall content score based on AEO signals.
    
    Args:
        faq_present: Whether FAQ section is present
        faq_schema_present: Whether FAQ schema is present
        question_headings: Number of question-based headings
        word_count: Total word count
        conversational_score: Count of conversational words
        featured_snippet_score: Count of featured snippet elements
        
    Returns:
        Content score as integer (0-100)
    """
    try:
        score = 0
        faq_points=0
        word_count_points=0
        # FAQ presence: up to 20 points
        if faq_present:
            faq_points += 10
        if faq_schema_present:
            faq_points += 10
        score += faq_points
        # Question headings: up to 20 points
        # Cap at 5 headings for full score
        question_points = min(question_headings, 5) * 4
        score += question_points
        
        # Word count: up to 20 points
        # Optimal range: 300-2000 words
        if word_count >= 2000:
            word_count_points += 20
        elif word_count >= 1000:
            word_count_points += 15
        elif word_count >= 500:
            word_count_points += 10
        elif word_count >= 300:
            word_count_points += 5
        score += word_count_points  
        # Conversational score: up to 20 points
        # Cap at 20 occurrences for full score
        conversational_points = int(min(conversational_score,20))
        score += conversational_points  
        # Featured snippet score: up to 20 points
        # Cap at 5 elements for full score
        snippet_points = min(featured_snippet_score, 5) * 4
        score += snippet_points
        
        # Ensure score is within 0-100 range
        breakdown = {
    "faq": faq_points,
    "questions": question_points,
    "word_count": word_count_points,
    "conversation": conversational_points,
    "snippets": snippet_points
}
        final_score = max(0,min(100, score))
        return final_score, breakdown 
        
    except Exception as e:

       logger.error(
        f"Error calculating content score: {e}",
        exc_info=True)

       return 0, {
        "faq": 0,
        "questions": 0,
        "word_count": 0,
        "conversation": 0,
        "snippets": 0
    }



