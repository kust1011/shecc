CFLAGS := -O -g \
	-std=c99 -pedantic

CFLAGS_TO_CHECK := \
	-fwrapv \
	-Wall -Wextra \
	-Wno-unused-but-set-variable \
	-Wno-unused-parameter \
	-Wno-unused-function \
	-Wshadow \
	-Wno-variadic-macros \
	-Wno-uninitialized \
	-Wno-strict-prototypes \
	-Wno-declaration-after-statement \
	-Wno-format \
	-Wno-format-pedantic \
	-Wno-overflow

SUPPORTED_CFLAGS :=
# Check if a specific compiler flag is supported, attempting a dummy compilation
# with flags. If successful, it returns the flag string; otherwise, it returns
# an empty string.
# Usage: $(call check_flag, -some-flag)
check_flag = $(shell $(CC) $(1) -S -o /dev/null -xc /dev/null 2>/dev/null; \
              if test $$? -eq 0; then echo "$(1)"; fi)

# Iterate through the list of all potential flags, effectively filtering out all
# unsupported flags.
$(foreach flag, $(CFLAGS_TO_CHECK), $(eval CFLAGS += $(call check_flag, $(flag))))

BUILD_SESSION := .session.mk

-include $(BUILD_SESSION)

STAGE0 := shecc
STAGE1 := shecc-stage1.elf
STAGE2 := shecc-stage2.elf

USE_QEMU ?= 1
OUT ?= out
ARCHS = arm riscv
ARCH ?= $(firstword $(ARCHS))
SRCDIR := $(shell find src -type d)
LIBDIR := $(shell find lib -type d)

BUILTIN_LIBC_SOURCE ?= c.c
BUILTIN_LIBC_HEADER := c.h
STAGE0_FLAGS ?= --dump-ir
STAGE1_FLAGS ?=
DYNLINK ?= 0
ifeq ($(DYNLINK),1)
    ifeq ($(ARCH),riscv)
        # TODO: implement dynamic linking for RISC-V.
        $(error "Dynamic linking mode is not implemented for RISC-V")
    endif
    STAGE0_FLAGS += --dynlink
    STAGE1_FLAGS += --dynlink
endif

SRCS := $(wildcard $(patsubst %,%/main.c, $(SRCDIR)))
OBJS := $(SRCS:%.c=$(OUT)/%.o)
deps := $(OBJS:%.o=%.o.d)
TESTS := $(wildcard tests/*.c)
TESTBINS := $(TESTS:%.c=$(OUT)/%.elf)
SNAPSHOTS = $(foreach SNAPSHOT_ARCH,$(ARCHS), $(patsubst tests/%.c, tests/snapshots/%-$(SNAPSHOT_ARCH)-static.json, $(TESTS)))
SNAPSHOTS += $(patsubst tests/%.c, tests/snapshots/%-arm-dynamic.json, $(TESTS))

BENCH_SCRIPT := scripts/benchmark.py
BENCH_OUTPUT_DIR ?= out/bench/latest
BENCH_PROFILE ?= full
BENCH_REPEAT ?= 5
BENCH_BASELINE_DIR ?= benchmarks/baselines
BENCH_WITH_LIBC ?= 0
BENCH_MEMORY_LIMIT_MB ?= 256
BENCH_RUNNER ?=
BENCH_LIBC_FLAG :=
ifeq ($(BENCH_WITH_LIBC),1)
BENCH_LIBC_FLAG := --with-libc
endif

all: config bootstrap

sanitizer: CFLAGS += -fsanitize=address -fsanitize=undefined -fno-omit-frame-pointer -O0
sanitizer: LDFLAGS += -fsanitize=address -fsanitize=undefined
sanitizer: config $(OUT)/$(STAGE0)-sanitizer
	$(VECHO) "  Built stage 0 compiler with sanitizers\n"

ifeq (,$(filter $(ARCH),$(ARCHS)))
$(error Support ARM and RISC-V only. Select the target with "ARCH=arm" or "ARCH=riscv")
endif
include mk/$(ARCH).mk
include mk/common.mk

config:
	$(Q)ln -s $(PWD)/$(SRCDIR)/$(ARCH)-codegen.c $(SRCDIR)/codegen.c
	$(Q)$(PRINTF) $(ARCH_DEFS) > $@
	$(VECHO) "Target machine code switch to %s\n" $(ARCH)
	$(Q)$(MAKE) $(BUILD_SESSION) --silent
	$(Q)$(CONFIG_CHECK_CMD)

$(OUT)/tests/%.elf: tests/%.c $(OUT)/$(STAGE0)
	$(VECHO) "  SHECC\t$@\n"
	$(Q)$(OUT)/$(STAGE0) $(STAGE0_FLAGS) -o $@ $< > $(basename $@).log ; \
	chmod +x $@ ; $(PRINTF) "Running $@ ...\n"
	$(Q)$(TARGET_EXEC) $@ && $(call pass)

check: check-stage0 check-stage2 check-abi-stage0 check-abi-stage2

check-stage0: $(OUT)/$(STAGE0) $(TESTBINS) tests/driver.sh
	$(VECHO) "  TEST STAGE 0\n"
	tests/driver.sh 0 $(DYNLINK)

check-stage2: $(OUT)/$(STAGE2) $(TESTBINS) tests/driver.sh
	$(VECHO) "  TEST STAGE 2\n"
	tests/driver.sh 2 $(DYNLINK)

check-sanitizer: $(OUT)/$(STAGE0)-sanitizer tests/driver.sh
	$(VECHO) "  TEST STAGE 0 (with sanitizers)\n"
	$(Q)cp $(OUT)/$(STAGE0)-sanitizer $(OUT)/shecc
	tests/driver.sh 0 $(DYNLINK)
	$(Q)rm $(OUT)/shecc

check-snapshots: $(OUT)/$(STAGE0) $(SNAPSHOTS) tests/check-snapshots.sh
	$(Q)$(foreach SNAPSHOT_ARCH, $(ARCHS), $(MAKE) distclean config check-snapshot ARCH=$(SNAPSHOT_ARCH) DYNLINK=0 --silent;)
	$(Q)$(MAKE) distclean config check-snapshot ARCH=arm DYNLINK=1 --silent
	$(VECHO) "Switching backend back to %s (DYNLINK=0)\n" arm
	$(Q)$(MAKE) distclean config ARCH=arm DYNLINK=0 --silent

check-snapshot: $(OUT)/$(STAGE0) tests/check-snapshots.sh
	$(VECHO) "Checking snapshot for %s (DYNLINK=%s)\n" $(ARCH) $(DYNLINK)
	tests/check-snapshots.sh $(ARCH) $(DYNLINK)
	$(VECHO) "  OK\n"

# TODO: Add an ABI conformance test suite for the RISC-V architecture
check-abi-stage0: $(OUT)/$(STAGE0)
	$(Q)if [ "$(ARCH)" = "arm" ]; then \
		tests/$(ARCH)-abi.sh 0 $(DYNLINK); \
	else \
		echo "Skip ABI compliance validation"; \
	fi

check-abi-stage2: $(OUT)/$(STAGE2)
	$(Q)if [ "$(ARCH)" = "arm" ]; then \
		tests/$(ARCH)-abi.sh 2 $(DYNLINK); \
	else \
		echo "Skip ABI compliance validation"; \
	fi

update-snapshots: tests/update-snapshots.sh
	$(Q)$(foreach SNAPSHOT_ARCH, $(ARCHS), $(MAKE) distclean config update-snapshot ARCH=$(SNAPSHOT_ARCH) DYNLINK=0 --silent;)
	$(Q)$(MAKE) distclean config update-snapshot ARCH=arm DYNLINK=1 --silent
	$(VECHO) "Switching backend back to %s (DYNLINK=0)\n" arm
	$(Q)$(MAKE) distclean config ARCH=arm DYNLINK=0 --silent

update-snapshot: $(OUT)/$(STAGE0) tests/update-snapshots.sh
	$(VECHO) "Updating snapshot for %s (DYNLINK=%s)\n" $(ARCH) $(DYNLINK)
	tests/update-snapshots.sh $(ARCH) $(DYNLINK)
	$(VECHO) "  OK\n"

bench-run: $(OUT)/$(STAGE0) $(BENCH_SCRIPT)
	$(VECHO) "Running benchmark profile=%s repeat=%s\n" $(BENCH_PROFILE) $(BENCH_REPEAT)
	$(Q)python3 $(BENCH_SCRIPT) run \
		--repo-root . \
		--shecc $(OUT)/$(STAGE0) \
		--runner "$(BENCH_RUNNER)" \
		--output-dir $(BENCH_OUTPUT_DIR) \
		--profile $(BENCH_PROFILE) \
		--repeat $(BENCH_REPEAT) $(BENCH_LIBC_FLAG)

bench-quick: $(OUT)/$(STAGE0) $(BENCH_SCRIPT)
	$(VECHO) "Running quick benchmark profile\n"
	$(Q)python3 $(BENCH_SCRIPT) run \
		--repo-root . \
		--shecc $(OUT)/$(STAGE0) \
		--runner "$(BENCH_RUNNER)" \
		--output-dir $(BENCH_OUTPUT_DIR) \
		--profile quick \
		--repeat 3 $(BENCH_LIBC_FLAG)

bench-issue297: $(OUT)/$(STAGE0) $(BENCH_SCRIPT)
	$(VECHO) "Running issue297 benchmark profile=%s repeat=%s\n" issue297 $(BENCH_REPEAT)
	$(Q)python3 $(BENCH_SCRIPT) run \
		--repo-root . \
		--shecc $(OUT)/$(STAGE0) \
		--runner "$(BENCH_RUNNER)" \
		--output-dir $(BENCH_OUTPUT_DIR) \
		--profile issue297 \
		--repeat $(BENCH_REPEAT) $(BENCH_LIBC_FLAG)

bench-memory-limit: $(OUT)/$(STAGE0) $(BENCH_SCRIPT)
	$(VECHO) "Running memory-limit benchmark (%s MiB)\n" $(BENCH_MEMORY_LIMIT_MB)
	$(Q)python3 $(BENCH_SCRIPT) run \
		--repo-root . \
		--shecc $(OUT)/$(STAGE0) \
		--runner "$(BENCH_RUNNER)" \
		--output-dir $(BENCH_OUTPUT_DIR) \
		--profile issue297 \
		--repeat 1 \
		--memory-limit-mb $(BENCH_MEMORY_LIMIT_MB) $(BENCH_LIBC_FLAG)

memcheck: $(OUT)/$(STAGE0) $(BENCH_SCRIPT)
	$(VECHO) "Running Valgrind memcheck on issue297 long program\n"
	$(Q)mkdir -p $(BENCH_OUTPUT_DIR)/bin
	$(Q)python3 $(BENCH_SCRIPT) prepare --repo-root . --output-dir $(BENCH_OUTPUT_DIR) --profile issue297
	$(Q)valgrind --leak-check=full --show-leak-kinds=all \
		--track-origins=yes \
		$(OUT)/$(STAGE0) --no-libc \
		-o $(BENCH_OUTPUT_DIR)/bin/memcheck-long.elf \
		$(BENCH_OUTPUT_DIR)/generated_sources/long_declarations_2000.c \
		> $(BENCH_OUTPUT_DIR)/memcheck.stdout.log \
		2> $(BENCH_OUTPUT_DIR)/memcheck.valgrind.log
	$(Q)grep -E "definitely lost:|indirectly lost:|ERROR SUMMARY:" \
		$(BENCH_OUTPUT_DIR)/memcheck.valgrind.log \
		> $(BENCH_OUTPUT_DIR)/memcheck.summary.txt

memcheck-strict: $(OUT)/$(STAGE0) $(BENCH_SCRIPT)
	$(VECHO) "Running strict Valgrind memcheck (fails on leaks)\n"
	$(Q)mkdir -p $(BENCH_OUTPUT_DIR)/bin
	$(Q)python3 $(BENCH_SCRIPT) prepare --repo-root . --output-dir $(BENCH_OUTPUT_DIR) --profile issue297
	$(Q)valgrind --leak-check=full --show-leak-kinds=all \
		--track-origins=yes --error-exitcode=1 \
		$(OUT)/$(STAGE0) --no-libc \
		-o $(BENCH_OUTPUT_DIR)/bin/memcheck-long.elf \
		$(BENCH_OUTPUT_DIR)/generated_sources/long_declarations_2000.c \
		> $(BENCH_OUTPUT_DIR)/memcheck.stdout.log \
		2> $(BENCH_OUTPUT_DIR)/memcheck.valgrind.log

massif: $(OUT)/$(STAGE0) $(BENCH_SCRIPT)
	$(VECHO) "Running Valgrind massif on issue297 long program\n"
	$(Q)mkdir -p $(BENCH_OUTPUT_DIR)/bin
	$(Q)python3 $(BENCH_SCRIPT) prepare --repo-root . --output-dir $(BENCH_OUTPUT_DIR) --profile issue297
	$(Q)valgrind --tool=massif --pages-as-heap=yes \
		--massif-out-file=$(BENCH_OUTPUT_DIR)/massif.out \
		$(OUT)/$(STAGE0) --no-libc \
		-o $(BENCH_OUTPUT_DIR)/bin/massif-long.elf \
		$(BENCH_OUTPUT_DIR)/generated_sources/long_declarations_2000.c \
		> $(BENCH_OUTPUT_DIR)/massif.stdout.log \
		2> $(BENCH_OUTPUT_DIR)/massif.stderr.log
	$(Q)ms_print $(BENCH_OUTPUT_DIR)/massif.out > $(BENCH_OUTPUT_DIR)/massif.report.txt

bench-save-baseline: bench-run
	$(Q)if [ -z "$(NAME)" ]; then \
		echo "Usage: make bench-save-baseline NAME=<label> [BENCH_PROFILE=full BENCH_REPEAT=5]"; \
		exit 1; \
	fi
	$(Q)mkdir -p $(BENCH_BASELINE_DIR)
	$(Q)cp $(BENCH_OUTPUT_DIR)/summary.json $(BENCH_BASELINE_DIR)/$(NAME).json
	$(Q)cp $(BENCH_OUTPUT_DIR)/summary.md $(BENCH_BASELINE_DIR)/$(NAME).md
	$(VECHO) "Saved baseline as %s/%s.json\n" $(BENCH_BASELINE_DIR) $(NAME)

bench-compare: $(BENCH_SCRIPT)
	$(Q)if [ -z "$(BASELINE)" ]; then \
		echo "Usage: make bench-compare BASELINE=<label>"; \
		echo "Expected file: $(BENCH_BASELINE_DIR)/<label>.json"; \
		exit 1; \
	fi
	$(Q)python3 $(BENCH_SCRIPT) compare \
		--baseline $(BENCH_BASELINE_DIR)/$(BASELINE).json \
		--current $(BENCH_OUTPUT_DIR)/summary.json \
		--output $(BENCH_OUTPUT_DIR)/comparison-$(BASELINE).md

$(OUT)/%.o: %.c
	$(VECHO) "  CC\t$@\n"
	$(Q)$(CC) -o $@ $(CFLAGS) -c -MMD -MF $@.d $<

SHELL_HACK := $(shell mkdir -p $(OUT) $(OUT)/$(SRCDIR) $(OUT)/tests)

$(OUT)/norm-lf: tools/norm-lf.c
	$(VECHO) "  CC+LD\t$@\n"
	$(Q)$(CC) $(CFLAGS) -o $@ $^

$(OUT)/libc.inc: $(OUT)/inliner $(OUT)/norm-lf $(LIBDIR)/$(BUILTIN_LIBC_SOURCE) $(LIBDIR)/$(BUILTIN_LIBC_HEADER)
	$(VECHO) "  GEN\t$@\n"
	$(Q)$(OUT)/norm-lf $(LIBDIR)/$(BUILTIN_LIBC_SOURCE) $(OUT)/c.normalized.c
	$(Q)$(OUT)/norm-lf $(LIBDIR)/$(BUILTIN_LIBC_HEADER) $(OUT)/c.normalized.h
	$(Q)$(OUT)/inliner $(OUT)/c.normalized.c $(OUT)/c.normalized.h $@
	$(Q)$(RM) $(OUT)/c.normalized.c $(OUT)/c.normalized.h

$(OUT)/inliner: tools/inliner.c
	$(VECHO) "  CC+LD\t$@\n"
	$(Q)$(CC) $(CFLAGS) -o $@ $^

$(OUT)/$(STAGE0): $(OUT)/libc.inc $(OBJS)
	$(VECHO) "  LD\t$@\n"
	$(Q)$(CC) $(OBJS) $(LDFLAGS) -o $@

$(OUT)/$(STAGE0)-sanitizer: $(OUT)/libc.inc $(OBJS)
	$(VECHO) "  LD\t$@ (with sanitizers)\n"
	$(Q)$(CC) $(OBJS) $(LDFLAGS) -o $@

$(OUT)/$(STAGE1): $(OUT)/$(STAGE0)
	$(Q)$(STAGE1_CHECK_CMD)
	$(VECHO) "  SHECC\t$@\n"
	$(Q)$(OUT)/$(STAGE0) $(STAGE0_FLAGS) -o $@ $(SRCDIR)/main.c > $(OUT)/shecc-stage1.log
	$(Q)chmod a+x $@

$(OUT)/$(STAGE2): $(OUT)/$(STAGE1)
	$(VECHO) "  SHECC\t$@\n"
	$(Q)$(TARGET_EXEC) $(OUT)/$(STAGE1) $(STAGE1_FLAGS) -o $@ $(SRCDIR)/main.c

bootstrap: $(OUT)/$(STAGE2)
	$(Q)chmod 775 $(OUT)/$(STAGE2)
	$(Q)if ! diff -q $(OUT)/$(STAGE1) $(OUT)/$(STAGE2); then \
	echo "Unable to bootstrap. Aborting"; false; \
	fi

$(BUILD_SESSION):
	$(PRINTF) "ARCH=$(ARCH)" > $@

.PHONY: clean bench-run bench-quick bench-issue297 bench-memory-limit memcheck memcheck-strict massif bench-save-baseline bench-compare
clean:
	-$(RM) $(OUT)/$(STAGE0) $(OUT)/$(STAGE1) $(OUT)/$(STAGE2)
	-$(RM) $(OBJS) $(deps)
	-$(RM) $(TESTBINS) $(OUT)/tests/*.log $(OUT)/tests/*.lst
	-$(RM) $(OUT)/shecc*.log
	-$(RM) $(OUT)/libc.inc

distclean: clean
	-$(RM) $(OUT)/inliner $(OUT)/norm-lf $(OUT)/target $(SRCDIR)/codegen.c config $(BUILD_SESSION)
	-$(RM) DOM.dot CFG.dot

-include $(deps)
