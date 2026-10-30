XELATEX = xelatex -interaction=nonstopmode -halt-on-error
TARGET = main
SECTIONS = $(wildcard sections/*.tex)

.PHONY: all clean

all: $(TARGET).pdf

$(TARGET).pdf: $(TARGET).tex $(SECTIONS)
	$(XELATEX) $(TARGET).tex
	$(XELATEX) $(TARGET).tex

clean:
	rm -f *.aux *.log *.out *.toc *.synctex.gz
