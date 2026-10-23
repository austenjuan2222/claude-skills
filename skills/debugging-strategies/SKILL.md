---
name: "debugging-strategies"
description: "Master systematic debugging techniques, profiling tools, and root cause analysis to efficiently track down bugs across any codebase or technology stack. Use when investigating bugs, performance issues, or unexpected behavior."
---

> Adapted from wshobson/agents (MIT). Reference file merged inline.

# Debugging Strategies

Transform debugging from frustrating guesswork into systematic problem-solving with proven strategies, powerful tools, and methodical approaches.

## When to Use This Skill

- Tracking down elusive bugs
- Investigating performance issues
- Understanding unfamiliar codebases
- Debugging production issues
- Analyzing crash dumps and stack traces
- Profiling application performance
- Investigating memory leaks
- Debugging distributed systems

## Core Principles

### 1. The Scientific Method

1. **Observe**: What's the actual behavior?
2. **Hypothesize**: What could be causing it?
3. **Experiment**: Test your hypothesis
4. **Analyze**: Did it prove/disprove your theory?
5. **Repeat**: Until you find the root cause

### 2. Debugging Mindset

**Don't Assume:**

- "It can't be X" - Yes it can
- "I didn't change Y" - Check anyway
- "It works on my machine" - Find out why

**Do:**

- Reproduce consistently
- Isolate the problem
- Keep detailed notes
- Question everything
- Take breaks when stuck

### 3. Rubber Duck Debugging

Explain your code and problem out loud (to a rubber duck, colleague, or yourself). Often reveals the issue.

## Systematic Debugging Process

### Phase 1: Reproduce

1. **Can you reproduce it?** Always? Sometimes? Randomly? Specific conditions? Can others reproduce it?
2. **Create minimal reproduction**: simplify to smallest example, remove unrelated code, isolate the problem
3. **Document steps**: exact steps, environment details, error messages

### Phase 2: Gather Information

1. **Error Messages**: full stack trace, error codes, console/log output
2. **Environment**: OS version, language/runtime version, dependency versions, environment variables
3. **Recent Changes**: git history, deployment timeline, configuration changes
4. **Scope**: all users or specific ones? all browsers? production only or also dev?

### Phase 3: Form Hypothesis

1. **What changed?** Recent code changes, dependency updates, infrastructure changes
2. **What's different?** Working vs broken environment, user, before vs after
3. **Where could this fail?** Input validation, business logic, data layer, external services

### Phase 4: Test & Verify

1. **Binary Search**: comment out half the code, narrow down, repeat
2. **Add Logging**: strategic console.log/print, track variable values, trace execution flow
3. **Isolate Components**: test each piece separately, mock dependencies, remove complexity
4. **Compare Working vs Broken**: diff configurations, environments, data

## Debugging Patterns by Issue Type

### Pattern 1: Intermittent Bugs

1. **Add extensive logging**: timing information, state transitions, external interactions
2. **Look for race conditions**: concurrent access to shared state, async operations out of order, missing synchronization
3. **Check timing dependencies**: setTimeout/setInterval, promise resolution order, animation frame timing
4. **Stress test**: run many times, vary timing, simulate load

### Pattern 2: Performance Issues

1. **Profile first**: don't optimize blindly, measure before and after, find bottlenecks
2. **Common culprits**: N+1 queries, unnecessary re-renders, large data processing, synchronous I/O
3. **Tools**: Browser DevTools Performance tab, Lighthouse, Python cProfile / line_profiler, Node clinic.js / 0x

### Pattern 3: Production Bugs

1. **Gather evidence**: error tracking (Sentry, Bugsnag), application logs, user reports, metrics
2. **Reproduce locally**: use production data (anonymized), match environment, follow exact steps
3. **Safe investigation**: don't change production, use feature flags, add monitoring/logging, test fixes in staging

## Tools and Techniques

### JavaScript/TypeScript Debugging

```typescript
function processOrder(order: Order) {
  debugger; // Execution pauses here
  const total = calculateTotal(order);
  console.log("Total:", total);
  if (order.items.length > 10) {
    debugger; // Only breaks if condition true
  }
  return total;
}

console.log("Value:", value);
console.table(arrayOfObjects);
console.time("operation"); /* code */ console.timeEnd("operation");
console.trace();
console.assert(value > 0, "Value must be positive");

performance.mark("start-operation");
// ... operation code
performance.mark("end-operation");
performance.measure("operation", "start-operation", "end-operation");
console.log(performance.getEntriesByType("measure"));
```

**VS Code Debugger Configuration (.vscode/launch.json):**

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "type": "node",
      "request": "launch",
      "name": "Debug Program",
      "program": "${workspaceFolder}/src/index.ts",
      "preLaunchTask": "tsc: build - tsconfig.json",
      "outFiles": ["${workspaceFolder}/dist/**/*.js"],
      "skipFiles": ["<node_internals>/**"]
    },
    {
      "type": "node",
      "request": "launch",
      "name": "Debug Tests",
      "program": "${workspaceFolder}/node_modules/jest/bin/jest",
      "args": ["--runInBand", "--no-cache"],
      "console": "integratedTerminal"
    }
  ]
}
```

### Python Debugging

```python
import pdb

def calculate_total(items):
    total = 0
    pdb.set_trace()  # Debugger starts here
    for item in items:
        total += item.price * item.quantity
    return total

def process_order(order):
    breakpoint()  # Python 3.7+

try:
    risky_operation()
except Exception:
    import pdb
    pdb.post_mortem()  # Debug at exception point

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def fetch_user(user_id):
    logger.debug(f'Fetching user: {user_id}')
    user = db.query(User).get(user_id)
    logger.debug(f'Found user: {user}')
    return user

import cProfile, pstats
cProfile.run('slow_function()', 'profile_stats')
stats = pstats.Stats('profile_stats')
stats.sort_stats('cumulative')
stats.print_stats(10)  # Top 10 slowest
```

### Go Debugging

```go
// Delve: go install github.com/go-delve/delve/cmd/dlv@latest ; dlv debug main.go
import (
    "fmt"
    _ "net/http/pprof"
    "os"
    "runtime/debug"
    "runtime/pprof"
)

func processRequest() {
    defer func() {
        if r := recover(); r != nil {
            fmt.Println("Panic:", r)
            debug.PrintStack()
            panic(r) // re-panic so callers still see the failure
        }
    }()
}

// The pprof blank import registers handlers on the default mux; serve it on a
// loopback-only endpoint before visiting http://localhost:6060/debug/pprof/.

func profileCPU() error {
    f, err := os.Create("cpu.prof")
    if err != nil {
        return err
    }
    defer f.Close()
    if err := pprof.StartCPUProfile(f); err != nil {
        return err
    }
    defer pprof.StopCPUProfile()
    return nil
}
```

### Technique 1: Binary Search Debugging (git bisect)

```bash
git bisect start
git bisect bad          # Current commit is bad
git bisect good v1.0.0  # v1.0.0 was good
# test each checked-out commit, then:
git bisect good   # if it works
git bisect bad    # if it's broken
git bisect reset  # when done
```

### Technique 2: Differential Debugging

| Aspect       | Working     | Broken         |
| ------------ | ----------- | -------------- |
| Environment  | Development | Production     |
| Node version | 18.16.0     | 18.15.0        |
| Data         | Empty DB    | 1M records     |
| User         | Admin       | Regular user   |
| Browser      | Chrome      | Safari         |
| Time         | During day  | After midnight |

Hypothesis: Time-based issue? Check timezone handling.

### Technique 3: Trace Debugging

```typescript
// legacy decorator signature: needs "experimentalDecorators": true
function trace(target: any, propertyKey: string, descriptor: PropertyDescriptor) {
  const originalMethod = descriptor.value;
  descriptor.value = function (...args: any[]) {
    console.log(`Calling ${propertyKey} with args:`, args);
    const result = originalMethod.apply(this, args);
    console.log(`${propertyKey} returned:`, result);
    return result;
  };
  return descriptor;
}
```

### Technique 4: Memory Leak Detection

```typescript
// Chrome DevTools: heap snapshot → perform action → snapshot again → compare
if (process.memoryUsage().heapUsed > 500 * 1024 * 1024) {
  console.warn("High memory usage:", process.memoryUsage());
  require("v8").writeHeapSnapshot();
}

let beforeMemory: number;
beforeEach(() => { beforeMemory = process.memoryUsage().heapUsed; });
afterEach(() => {
  const diff = process.memoryUsage().heapUsed - beforeMemory;
  if (diff > 10 * 1024 * 1024) console.warn(`Possible memory leak: ${diff / 1024 / 1024}MB`);
});
```

## Best Practices

1. **Reproduce First**: Can't fix what you can't reproduce
2. **Isolate the Problem**: Remove complexity until minimal case
3. **Read Error Messages**: They're usually helpful
4. **Check Recent Changes**: Most bugs are recent
5. **Use Version Control**: Git bisect, blame, history
6. **Take Breaks**: Fresh eyes see better
7. **Document Findings**: Help future you
8. **Fix Root Cause**: Not just symptoms

## Common Debugging Mistakes

- **Making Multiple Changes**: Change one thing at a time
- **Not Reading Error Messages**: Read the full stack trace
- **Assuming It's Complex**: Often it's simple
- **Debug Logging in Prod**: Remove before shipping
- **Not Using Debugger**: console.log isn't always best
- **Giving Up Too Soon**: Persistence pays off
- **Not Testing the Fix**: Verify it actually works

## Quick Debugging Checklist

- [ ] Spelling errors (typos in variable names)
- [ ] Case sensitivity (fileName vs filename)
- [ ] Null/undefined values
- [ ] Array index off-by-one
- [ ] Async timing (race conditions)
- [ ] Scope issues (closure, hoisting)
- [ ] Type mismatches
- [ ] Missing dependencies
- [ ] Environment variables
- [ ] File paths (absolute vs relative)
- [ ] Cache issues (clear cache)
- [ ] Stale data (refresh database)