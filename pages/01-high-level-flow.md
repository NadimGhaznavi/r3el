# 3 Loops

## DISCOVERY / IDENTIFICATION LOOP

filesystem -> Qwen -> TMDB -> proposed record -> queue

## REVIEW LOOP

human -> approve / reject / modify

## EXECUTION LOOP

approved queue -> filesystem operations -> DB finalization

# Batching with a Human-in-the-Loop

```
R3el fills batch
       ↓
batch = REVIEWING
       ↓
you approve/reject/modify 73 items
       ↓
SUBMIT
       ↓
batch = COMMITTED
       ↓
execute approved filesystem operations
       ↓
record success/failure per item
       ↓
batch = COMPLETE
       ↓
R3el starts filling the next batch
```