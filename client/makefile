include ../make.cfg
.PHONY: all 

TARGETS=$(patsubst %,cgosGtp-%,$(TARGET_PLATFORMS)) cgosGtp.kit

all: $(TARGETS)

cgosGtp-% : cgosGtp.vfs/lib/app-cgosGtp/cgosGtp.tcl
	$(SDX) wrap cgosGtp.tmp -runtime ../third_party/tclkits/tclkit-$(patsubst cgosGtp-%,%,$@)
	mv cgosGtp.tmp $@

cgosGtp.kit: cgosGtp.vfs/lib/app-cgosGtp/cgosGtp.tcl
	$(SDX) wrap cgosGtp.kit

cgosGtp.vfs/lib/app-cgosGtp/cgosGtp.tcl: cgosGtp.tcl

	cp cgosGtp.tcl cgosGtp.vfs/lib/app-cgosGtp/cgosGtp.tcl

.PHONY:
clean:
	rm -f $(TARGETS) cgosGtp.tmp
