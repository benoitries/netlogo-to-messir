# Audit des différences entre fichiers input-instructions*.md

**Date**: 2025-01-27  
**Raison**: Problème de synchronisation OneDrive créant des doublons

## Résumé exécutif

Les fichiers `input-instructions*.md` sont des **artefacts de sortie générés automatiquement** (pas du code source). Ils contiennent les prompts complets envoyés aux modèles pour le debugging. Les suffixes comme `UNIWHV23P65G0` sont des identifiants uniques d'exécutions différentes.

**Conclusion**: Ces fichiers sont des artefacts temporaires de debugging. Aucun contenu important ne doit être intégré. Ils peuvent être supprimés ou archivés.

## Analyse des fichiers

### 1. `input-instructions.md` (version normale)

**Type**: PlantUML Diagram Auditor  
**Contenu**:
- Persona: `PSN-LUCIM-PLANTUML-DIAGRAM-AUDITOR`
- Diagramme PlantUML complet avec:
  - Participants: System, ActClock, ActEnvironment, ActAdministrator, ActEndUser
  - Messages complets avec activations
  - Configuration de style (skinparam)

**Statut**: ✅ Fichier de sortie normal (généré par `write_input_instructions_before_api()`)

### 2. `input-instructions-UNIQ6QJ9W9F3F.md`

**Type**: Operation Model Auditor  
**Contenu**:
- Persona: `PSN-LUCIM-OPERATION-MODEL-AUDITOR`
- Règles: `RULES-LUCIM-OPERATION-MODEL` (LEM1-LEM5)
- **Modèle vide**: `{}` (ligne 122)

**Statut**: ⚠️ Artefact d'exécution avec modèle vide (probablement première itération)

### 3. `input-instructions-UNIWHV23P65G0-3.md`

**Type**: Operation Model Auditor  
**Contenu**:
- Persona: `PSN-LUCIM-OPERATION-MODEL-AUDITOR`
- Règles: `RULES-LUCIM-OPERATION-MODEL` (LEM1-LEM5)
- **Modèle complet** avec:
  - ActEnvironment (oeSimulateRain)
  - ActAdministrator (ieHpcInstalled, oeInstallHpc)
  - ActEndUser (multiple IE/OE events)

**Statut**: ⚠️ Artefact d'exécution avec modèle complet (probablement itération suivante)

### 4. `input-instructions-UNIWHV23P65G0-2.md`

**Type**: Scenario Auditor  
**Contenu**:
- Persona: `PSN-LUCIM-SCENARIO-AUDITOR`
- Règles: `RULES-LUCIM-SCENARIO` (LEM3, LEM4, LEM6, AS3, AS4, AS6, CONS1-3)
- **Scénario complet** avec 8 messages:
  - ActMsrCreator -> System : oeCreateSystemAndEnvironment
  - ActClock -> System : oeSetClock, oeAdvanceTick
  - ActEnvironment -> System : oeSimulateRain
  - ActAdministrator -> System : oeInstallHpc
  - System -> ActAdministrator : ieHpcInstallationComplete
  - System -> ActEndUser : ieHpcInstallationComplete, ieRainExtreme, ieElectionDay

**Statut**: ⚠️ Artefact d'exécution avec scénario complet

### 5. `input-instructions-UNIWHV23P65G0.md`

**Type**: Scenario Auditor  
**Contenu**:
- Persona: `PSN-LUCIM-SCENARIO-AUDITOR`
- Règles: `RULES-LUCIM-SCENARIO` (mêmes règles)
- **Scénario vide**: 13 lignes avec `->  : (...)` (lignes 130-143)

**Statut**: ⚠️ Artefact d'exécution avec scénario vide (probablement première itération)

## Différences identifiées

### Différences structurelles

1. **Types d'agents différents**:
   - PlantUML Diagram Auditor (fichier normal)
   - Operation Model Auditor (UNIQ6QJ9W9F3F, UNIWHV23P65G0-3)
   - Scenario Auditor (UNIWHV23P65G0-2, UNIWHV23P65G0)

2. **Contenu des données**:
   - Fichier normal: Diagramme PlantUML complet
   - UNIQ6QJ9W9F3F: Modèle vide `{}`
   - UNIWHV23P65G0-3: Modèle complet avec acteurs
   - UNIWHV23P65G0-2: Scénario complet avec 8 messages
   - UNIWHV23P65G0: Scénario vide avec placeholders

3. **Règles différentes**:
   - PlantUML: Règles AS, SS, TCS, GCS, NAM (non visibles dans le fichier normal)
   - Operation Model: Règles LEM1-LEM5
   - Scenario: Règles LEM3, LEM4, LEM6, AS3, AS4, AS6, CONS1-3

### Différences de contenu

**Aucune différence structurelle importante** dans les personas ou les formats de sortie. Les différences sont uniquement:
- Le type d'agent (persona différente)
- Le contenu des données (vide vs complet)
- Les règles spécifiques à chaque type d'audit

## Recommandations

### ✅ Actions recommandées

1. **Conserver le fichier normal** (`input-instructions.md`) si nécessaire pour référence
2. **Supprimer les fichiers avec suffixes UNIWH/UNIQ** - ce sont des artefacts d'exécutions passées
3. **Aucune intégration nécessaire** - les fichiers sont des artefacts de debugging, pas du code source

### 🗑️ Fichiers à supprimer (artefacts temporaires)

```
- input-instructions-UNIQ6QJ9W9F3F.md
- input-instructions-UNIWHV23P65G0-3.md
- input-instructions-UNIWHV23P65G0-2.md
- input-instructions-UNIWHV23P65G0.md
```

### 📝 Note importante

Ces fichiers sont générés automatiquement par `write_input_instructions_before_api()` dans `utils_response_dump.py`. Ils sont écrits dans le répertoire `output_dir` passé à chaque agent. Les fichiers avec suffixes sont probablement:
- Des exécutions différentes (différents runs)
- Des fichiers renommés manuellement
- Des artefacts de synchronisation OneDrive

**Ils ne doivent PAS être versionnés** (devraient être dans `.gitignore`).

## Conclusion

Les fichiers `input-instructions*.md` sont des **artefacts de debugging temporaires**. Aucun contenu important ne doit être intégré. Les fichiers avec suffixes UNIWH/UNIQ peuvent être supprimés en toute sécurité. Le fichier normal (`input-instructions.md`) peut être conservé pour référence si nécessaire, mais devrait idéalement être dans `.gitignore`.

