include ../make.cfg

TARGETS=$(patsubst %,cgosview-%,$(TARGET_PLATFORMS))

.PHONY:
all: $(TARGETS)

CGOSVIEWER_SOURCE = $(wildcard cgosviewer.vfs/main.tcl cgosviewer.vfs/lib/*/*)

cgosview-%: $(CGOSVIEWER_SOURCE)
	$(SDX) wrap cgosview.tmp -runtime ../third_party/tclkits/tclkit-$(patsubst cgosview-%,%,$@)
	mv cgosview.tmp $@

.PHONY:
clean:
	rm -f $(TARGETS) cgosview.tmp
