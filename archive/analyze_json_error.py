#!/usr/bin/env python3
"""Analyze JSON parsing error in corrector output."""
import json
import sys

# Lire le fichier raw response
import pathlib
script_dir = pathlib.Path(__file__).parent
file_path = script_dir / 'output/runs/2025-11-01/0729-persona-v3-limited-agents-v3-no-adk/3d-solids-gpt-5-mini-reason-low-verb-medium/05-plantuml_lucim_corrector/output-raw_response.json'

with open(file_path, 'r') as f:
    raw_data = json.load(f)

# Extraire le texte JSON généré par le LLM
output_text = raw_data['output'][1]['content'][0]['text']
print('=== Analyse du JSON généré par le LLM ===')
print(f'Longueur totale: {len(output_text)} caractères')
print()

# Nettoyer comme le fait le code Python
content_clean = output_text.strip()
if content_clean.startswith('```json'):
    content_clean = content_clean.replace('```json', '').replace('```', '').strip()
elif content_clean.startswith('```'):
    content_clean = content_clean.replace('```', '').strip()

print('=== Tentative de parsing JSON ===')
try:
    # Chercher le caractère problématique autour de la position 2893
    char_pos = 2893
    start = max(0, char_pos - 100)
    end = min(len(content_clean), char_pos + 100)
    print(f'Caractères autour de la position {char_pos}:')
    print(repr(content_clean[start:end]))
    print()
    
    # Afficher les caractères autour de la position avec leurs codes
    print('Codes ASCII des caractères problématiques:')
    for i in range(max(0, char_pos - 20), min(char_pos + 20, len(content_clean))):
        char = content_clean[i]
        code = ord(char)
        marker = ' <-- PROBLÈME ICI' if i == char_pos else ''
        if code < 32 or code > 126:
            print(f'  Position {i}: {repr(char)} (ASCII {code}){marker}')
    print()
    
    # Essayer de parser
    parsed = json.loads(content_clean)
    print('✅ JSON valide!')
except json.JSONDecodeError as e:
    print(f'❌ Erreur de parsing: {e}')
    print(f'   Position: {e.pos}')
    print(f'   Ligne: {e.lineno}')
    print(f'   Colonne: {e.colno}')
    print()
    
    # Afficher le contexte autour de l'erreur
    if e.pos < len(content_clean):
        start = max(0, e.pos - 150)
        end = min(len(content_clean), e.pos + 150)
        print(f'Contexte autour de l\'erreur (position {e.pos}):')
        context = content_clean[start:end]
        print(repr(context))
        print()
        print('Contexte lisible:')
        # Remplacer les caractères non-printables par leur représentation
        readable = ''.join(c if 32 <= ord(c) <= 126 or c in '\n\r\t' else f'<{ord(c)}>' for c in context)
        print(readable)
        print()
        
        # Identifier les caractères de contrôle invalides
        print('Caractères de contrôle invalides trouvés:')
        for i in range(start, min(end, len(content_clean))):
            char = content_clean[i]
            code = ord(char)
            # JSON ne permet que \n, \r, \t comme caractères de contrôle
            if code < 32 and char not in '\n\r\t':
                print(f'  Position {i}: {repr(char)} (ASCII {code}) - INVALIDE pour JSON')

