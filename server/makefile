include ../make.cfg

TARGETS=$(patsubst %,cgos-%,$(TARGET_PLATFORMS)) \
	$(patsubst %,webuild-%,$(TARGET_PLATFORMS))

.PHONY:
all: $(TARGETS)

CGOS_SOURCE = $(wildcard cgos.vfs/main.tcl cgos.vfs/lib/*/*)
WEBUILD_SOURCE = $(wildcard webuild.vfs/main.tcl webuild.vfs/lib/*/*)

cgos-%: $(CGOS_SOURCE)
	$(SDX) wrap cgos.tmp -runtime ../third_party/tclkits/tclkit-$(patsubst cgos-%,%,$@)
	mv cgos.tmp $@

webuild-%: $(WEBUILD_SOURCE)
	$(SDX) wrap webuild.tmp -runtime ../third_party/tclkits/tclkit-$(patsubst webuild-%,%,$@)
	mv webuild.tmp $@

.PHONY:
clean:
	rm -f $(TARGETS) cgos.tmp webuild.tmp
