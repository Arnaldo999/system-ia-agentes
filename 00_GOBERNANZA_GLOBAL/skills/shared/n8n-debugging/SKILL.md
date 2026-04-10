---
name: n8n-debugging
description: Debug n8n workflows and code nodes. Use when a workflow fails, a Code node throws an error, expressions return unexpected values, data is missing or malformed, or when you need to inspect data at any point in a workflow.
---

# n8n Debugging

Expert guide for debugging n8n workflows, code nodes, and expressions.

---

## Quick Diagnosis Checklist

When something fails, check in this order:

1. **Read the error message** - n8n usually tells you exactly what failed
2. **Check the execution log** - See which node failed and its input/output
3. **Inspect the data** - Pin data and use the expression editor to test
4. **Isolate the problem** - Test the failing node alone with sample data
5. **Add console.log** in Code nodes to trace values

---

## Reading Execution Logs

### Where to Find Them

- **Manual executions**: Click the node after running to see Input/Output tabs
- **Past executions**: Workflow → Executions tab → Click any execution
- **Error executions**: Filter by "Error" status

### What to Look For

```
Input Data  → What the node received
Output Data → What the node produced
Error       → Error message + stack trace
```

**Key**: Compare Input vs Output to understand transformations.

---

## Debugging Code Nodes

### console.log() - Most Useful Tool

Output appears in **n8n execution log** (browser dev tools F12 Console tab):

```javascript
const items = $input.all();

// Log count
console.log(`Items received: ${items.length}`);

// Log full structure of first item
console.log('First item:', JSON.stringify(items[0], null, 2));

// Log specific field
console.log('Email:', items[0].json.email);

// Log before/after transformation
const raw = items[0].json;
console.log('Raw:', raw);

const processed = { name: raw.name?.trim(), email: raw.email?.toLowerCase() };
console.log('Processed:', processed);

return [{ json: processed }];
```

### Inspect Data Structure

```javascript
// Dump entire input to see full structure
const items = $input.all();
const structure = items.map(item => ({
  json: item.json,
  binary: item.binary ? Object.keys(item.binary) : null,
  hasPairedItem: !!item.pairedItem
}));

console.log('Full structure:', JSON.stringify(structure, null, 2));
return items; // Pass through unchanged
```

### Trace Webhook Data

```javascript
// When webhook data is missing, dump everything
const item = $input.first();
console.log('All json keys:', Object.keys(item.json));
console.log('body:', item.json.body);
console.log('headers:', item.json.headers);
console.log('query:', item.json.query);

return [{ json: { debug: true } }];
```

### Find Undefined Values

```javascript
const items = $input.all();

const debugInfo = items.map((item, index) => {
  const data = item.json;
  const missingFields = [];

  // Check expected fields
  ['name', 'email', 'id', 'status'].forEach(field => {
    if (data[field] === undefined || data[field] === null) {
      missingFields.push(field);
    }
  });

  return {
    json: {
      index,
      missingFields,
      hasAllRequired: missingFields.length === 0,
      data
    }
  };
});

return debugInfo;
```

### Safe Type Inspection

```javascript
// When you don't know the type of a value
function inspect(value) {
  if (value === null) return 'null';
  if (value === undefined) return 'undefined';
  if (Array.isArray(value)) return `Array[${value.length}]`;
  return typeof value;
}

const item = $input.first();
const data = item.json;

return [{
  json: {
    type_of_data: inspect(data),
    type_of_body: inspect(data.body),
    type_of_items: inspect(data.items),
    keys: typeof data === 'object' ? Object.keys(data) : []
  }
}];
```

---

## Debugging Expressions

### Expression Editor (Live Preview)

1. Click any field that accepts expressions
2. Click the **"fx"** icon to open expression editor
3. Type your expression → see **live result** on the right
4. Check for red error highlighting

**Test expressions interactively** before putting them in workflow.

### Common Expression Debug Patterns

```javascript
// Check if field exists before using it
{{$json.user?.email ?? 'NO EMAIL'}}

// Show what type a value is
{{typeof $json.value}}

// Show array length
{{($json.items || []).length}}

// Reveal full object as string
{{JSON.stringify($json.body)}}

// Check nested path step by step
{{$json.body}}                   // First check body exists
{{$json.body?.user}}             // Then check user
{{$json.body?.user?.email}}      // Then check email
```

### Debug a Failed Node Reference

```javascript
// If $node["My Node"] throws error, first verify it exists
{{Object.keys($node).join(', ')}}  // See all available node names
```

---

## Pin Data for Testing

**Pin Data** = freeze a node's output so you can test downstream nodes without re-running the whole workflow.

### How to Use

1. Run the workflow (or trigger manually)
2. Click the node you want to freeze
3. Click **"Pin Data"** button (pin icon)
4. Now downstream nodes use this frozen data
5. Edit and test downstream nodes freely

### Best for:
- Testing Code nodes without re-calling external APIs
- Testing with specific edge cases (empty arrays, null values, etc.)
- Developing against webhook data without re-triggering

### Simulate Problem Data

Create a **Manual Trigger → Set node** with test data that mimics real input:

```javascript
// In Set node (using expression mode):
// name: "Test User"
// email: null         ← test missing email
// items: []           ← test empty array
// status: "INVALID"   ← test bad status
```

---

## Error Message Interpretation

### "Cannot read properties of undefined"
```
Error: Cannot read properties of undefined (reading 'email')
```
**Cause**: Trying to access `.email` on `undefined`
**Fix**: Check parent field exists first
```javascript
// ❌ Fails if user is undefined
const email = $json.user.email;

// ✅ Safe access
const email = $json?.user?.email ?? 'default@example.com';
```

### "item.json is undefined"
**Cause**: You called `$input.all()` but used wrong property path
**Fix**:
```javascript
// ❌ Wrong
const items = $input.all();
const email = items[0].email; // Missing .json!

// ✅ Correct
const email = items[0].json.email;
```

### "Return value is not valid"
**Cause**: Code node not returning correct format
**Fix**:
```javascript
// ❌ Common mistakes
return "string";              // Not array
return { json: {} };          // Not array
return [{ data: {} }];        // Missing 'json' key

// ✅ Correct format
return [{ json: { result: 'value' } }];
```

### "Expression Error: $json.x is not defined"
**Cause**: Accessing field that doesn't exist in current node's data
**Fix**: Check data flow - which node produces this data? Use `$node["NodeName"].json.x` if it's from a different node.

### HTTP 401/403 Errors
**Cause**: Authentication failing
**Debug**:
```javascript
// Log the headers being sent
const response = await $helpers.httpRequest({
  url: 'https://api.example.com',
  headers: { 'Authorization': 'Bearer token' }
});
console.log('Response status:', response.statusCode);
console.log('Response body:', response.body);
```

### "Module not found" (Python)
**Cause**: Trying to import external library (only stdlib allowed in Python)
**Fix**: Switch to JavaScript or use HTTP Request node for external calls.

---

## Debugging Workflow-Level Issues

### Check Node Execution Order

```
Workflow Settings → Execution Order
```
- **v0** (legacy): Top-to-bottom
- **v1** (recommended): Connection-based

If nodes run in wrong order → check connections and switch to v1.

### Find Why a Branch Doesn't Execute

IF node has two outputs (true/false). If one branch never runs:
1. Click the IF node after execution
2. Check **Output 1 (true)** and **Output 2 (false)** tabs
3. See which items went where
4. Check your condition logic

```javascript
// Test your IF condition in a Code node first
const items = $input.all();
return items.map(item => ({
  json: {
    ...item.json,
    conditionResult: item.json.status === 'active',  // Debug the condition
    conditionValue: item.json.status                  // See actual value
  }
}));
```

### Debug Loop / Split in Batches

```javascript
// In Code node inside loop
return [{
  json: {
    currentBatch: $runIndex,
    itemsInThisBatch: $input.all().length,
    firstItemId: $input.first()?.json?.id
  }
}];
```

### Find Missing Data in Merge Node

When Merge produces fewer items than expected:
```javascript
// After merge node, check what came through
const items = $input.all();
return [{
  json: {
    totalItemsAfterMerge: items.length,
    ids: items.map(i => i.json.id),
    sample: items[0]?.json
  }
}];
```

---

## Debugging AI Agent Workflows

### Log AI Tool Calls

Add a Code node as a pass-through before AI tool inputs:

```javascript
const item = $input.first();
console.log('Tool called with:', JSON.stringify(item.json, null, 2));
return [{ json: item.json }];
```

### Inspect AI Response Structure

```javascript
const response = $input.first().json;
console.log('AI response keys:', Object.keys(response));
console.log('Output:', response.output || response.text || response.content);

return [{
  json: {
    hasOutput: !!response.output,
    hasText: !!response.text,
    keys: Object.keys(response)
  }
}];
```

---

## Debugging Strategy by Symptom

| Symptom | First Action |
|---------|-------------|
| Node fails with error | Read error message, check node's Input tab |
| Wrong data in output | Add `console.log` before return, check Input vs Output tabs |
| Expression shows as text | Add `{{` `}}` around expression |
| `undefined` everywhere | Check data flow, verify field names with expression editor |
| Missing items after IF | Check condition in expression editor, test with real values |
| Webhook data missing | Access via `$json.body.field`, not `$json.field` |
| Loop runs wrong times | Check Split in Batches `Batch Size` setting |
| Merge has wrong count | Check that both input branches produce items |
| AI not using tools | Check tool node connections (ai_tool type) |

---

## Best Practices

### ✅ Do

- Use **Pin Data** heavily during development
- Add `console.log` as first debugging step in Code nodes
- Test expressions in the **Expression Editor** before putting them in nodes
- Check node **Input/Output tabs** after each execution
- Add a **Set node** after complex transforms to verify data shape
- Use the **Execution Log** to trace where issues start

### ❌ Don't

- Debug by repeatedly triggering real webhooks (use Pin Data instead)
- Delete a node to "fix" it before understanding why it failed
- Assume the data structure — always inspect it first
- Ignore warnings in the execution log
- Test with live production data when sample data will do

---

## Related Skills

- **n8n Code JavaScript** - Write correct JS code to avoid debugging needs
- **n8n Expression Syntax** - Fix expression errors
- **n8n Validation Expert** - Pre-deployment validation to catch errors early
- **n8n Workflow Patterns** - Use proven patterns that avoid common pitfalls