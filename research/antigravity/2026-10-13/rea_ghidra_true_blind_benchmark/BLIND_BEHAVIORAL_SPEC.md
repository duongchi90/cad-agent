# BLIND_BEHAVIORAL_SPEC: Clean-Room Behavioral Specification of Wallace Target

- **Document ID:** `REA_TRUE_BLIND_SPEC_V1`
- **Executor Role:** `ANTIGRAVITY_REA_BENCHMARK_AUDITOR_AND_TRUE_BLIND_VALIDATOR`
- **Workstation Role:** `ANTI_HOME_RESEARCH_MACHINE`
- **Project:** `duongchi90/cad-agent`
- **Pre-Reveal Status:** STRICTLY_FROZEN (Synthesized prior to opening source files)

---

## 1. Clean-Room Architectural Model

Based entirely on Ghidra 12.1.4 decompilation and xrefs without source access:

### A. Data Types & Layouts

```cpp
// Estimated size: 44 bytes (0x2C)
struct Character {
    int id;               // offset 0x00: index assigned during processing
    char name[32];        // offset 0x04: fixed character name string
    bool is_special;      // offset 0x24: flag (V1: rand coin-flip, V2: id % 3 == 0)
    Character* next;      // offset 0x28: singly-linked list next pointer
};

// Estimated size: 16 bytes (0x10)
class Device {
public:
    const char* name;     // offset 0x00: "Infrared Garden Gnome"
    int unknown_field;    // offset 0x04: 0
    bool is_deployed;     // offset 0x08: 0 (false) or 1 (true)
    Character* target;    // offset 0x0C: pointer to deployed character

    Device(const char* device_name) {
        name = device_name;
        unknown_field = 0;
        is_deployed = false;
        target = nullptr;
    }

    void deploy(Character* char_target) {
        if (!is_deployed) {
            is_deployed = true;
            target = char_target;
        }
    }

    void print_status() {
        const char* status = is_deployed ? "is" : "is not";
        const char* target_name = is_deployed ? target->name : "anyone";
        printf("%s %s deployed on %s\n", name, status, target_name);
    }
};
```

---

## 2. Program Execution Pipeline (`main`)

```cpp
Character* g_character_list = nullptr;

void init_characters(Character** head) {
    // Prepends nodes so reverse order appears at head
    character_create_and_prepend(head, "Lord Victor Quartermaine");
    character_create_and_prepend(head, "Lady Tottington");
    character_create_and_prepend(head, "Were Rabbit");
    character_create_and_prepend(head, "Rabbit");
    character_create_and_prepend(head, "Gromit");
    character_create_and_prepend(head, "Wallace");
}

void process_characters(Character* head) {
    int id = 0;
    for (Character* curr = head; curr != nullptr; curr = curr->next) {
        curr->id = id++;
        // V1 behavior:
        curr->is_special = (rand() * 2 < 1);
        // V2 behavior:
        // curr->is_special = (curr->id % 3 == 0);
    }
}

Device* create_and_deploy_device(Character* head) {
    Device* dev = new Device("Infrared Garden Gnome");
    for (Character* curr = head; curr != nullptr; curr = curr->next) {
        // V1 behavior:
        if (strcmp(curr->name, "Wallace") == 0) {
            dev->deploy(curr);
        }
        // V2 behavior:
        // if (strcmp(curr->name, "Wallace") == 0 || curr->is_special) {
        //     dev->deploy(curr);
        // }
    }
    return dev;
}

int main() {
    init_characters(&g_character_list);
    process_characters(g_character_list);
    Device* dev = create_and_deploy_device(g_character_list);
    dev->print_status();
    return 0;
}
```

---

## 3. Predicted Program Output

### Version 1 (`WallaceSrc.exe`):
Always searches for `"Wallace"`. Because `"Wallace"` is the first node encountered in the list (`Wallace` $\to$ `Gromit` $\to$ ...), `dev->deploy(curr)` is called on `Wallace`.
Output:
```text
Infrared Garden Gnome is deployed on Wallace
```

### Version 2 (`WallaceVersion2.exe`):
Searches for `"Wallace"` OR `curr->is_special`. Since `Wallace` has `id = 0`, `0 % 3 == 0` is true, so `is_special` is true. `Wallace` matches both conditions.
Output:
```text
Infrared Garden Gnome is deployed on Wallace
```
