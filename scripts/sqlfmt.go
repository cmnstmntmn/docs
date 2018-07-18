package main

import (
	"bytes"
	"fmt"
	"io/ioutil"
	"os"
	"path/filepath"
	"regexp"
	"strings"

	"github.com/cockroachdb/cockroach/pkg/sql/parser"
	"github.com/cockroachdb/cockroach/pkg/sql/sem/tree"
	// Initialize the builtins.
	_ "github.com/cockroachdb/cockroach/pkg/sql/sem/builtins"
)

func main() {
	sqlRE := regexp.MustCompile(`(?is)(~~~.?sql)(.*?)(~~~)`)
	exprRE := regexp.MustCompile(`(\s*>\s*)((?s).*?)(?:;?)(\s*(?:--.*?))`)
	cfg := tree.DefaultPrettyCfg()
	cfg.LineWidth = 80
	var eb bytes.Buffer
	err := filepath.Walk(".", func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if info.IsDir() || !strings.HasSuffix(path, ".md") {
			return nil
		}
		b, err := ioutil.ReadFile(path)
		if err != nil {
			return err
		}
		n := sqlRE.ReplaceAllFunc(b, func(found []byte) []byte {
			blockMatch := sqlRE.FindSubmatch(found)
			var buf bytes.Buffer
			buf.Write(blockMatch[1])
			mid := exprRE.ReplaceAllFunc(blockMatch[2], func(expr []byte) []byte {
				exprMatch := exprRE.FindSubmatch(expr)
				s, err := parser.ParseOne(string(exprMatch[2]))
				if err != nil {
					return expr
				}
				eb.Reset()
				eb.Write(exprMatch[1])
				eb.WriteString(cfg.Pretty(s))
				eb.WriteByte(';')
				eb.Write(exprMatch[3])
				return eb.Bytes()
			})
			buf.Write(mid)
			buf.Write(blockMatch[3])
			return buf.Bytes()
		})
		if bytes.Equal(b, n) {
			return nil
		}
		return ioutil.WriteFile(path, n, 0666)
	})
	if err != nil {
		fmt.Println(err)
	}
}
