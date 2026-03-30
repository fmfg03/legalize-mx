# Project-Scoped Claude Context

Esto no replica `/root/.claude` completo.

Replica el subconjunto portable que aporta disciplina de trabajo, comandos reutilizables y agentes relevantes a `legalize-mx`.

## Incluido

1. `CLAUDE.md`
2. `commands/`
3. `agents/core/`
4. `agents/domains/`
5. `agents/RAG/`

## Excluido

1. `sessions/` globales completas
2. `projects/`
3. `cache/`
4. `memory/`
5. `enhanced-memory/`
6. `analytics/`
7. `telemetry/`
8. `agents_backup*`
9. `settings.local.json`

## Razon

`projects`, `memory`, `sessions` globales y `cache` arrastran ruido operativo y estado no portable. `legalize-mx` necesita contexto reutilizable, no residuos de ejecución.

## Refresco

```bash
cp /root/.claude/CLAUDE.md /root/legalize-mx/.claude/CLAUDE.md
cp -a /root/.claude/commands /root/legalize-mx/.claude/
cp -a /root/.claude/agents/core /root/legalize-mx/.claude/agents/
cp -a /root/.claude/agents/domains /root/legalize-mx/.claude/agents/
cp -a /root/.claude/agents/RAG /root/legalize-mx/.claude/agents/
```
