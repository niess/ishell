.PHONY: bin clean lib update_submodules

bin: bin/iinit bin/ishell

bin/%: scripts/%.py lib
	@mkdir -p bin
	@cp -f $< $@

clean:
	@rm -rf bin lib/python/irods lib/python/six.py lib/python/*.pyc

lib: lib/python/irods lib/python/six.py

lib/python/irods: deps/python-irodsclient/irods
	@rm -f $@
	@cd lib/python && ln -s ../../$< irods

lib/python/six.py: deps/six/six.py
	@rm -f $@
	@cd lib/python && ln -s ../../$< six.py

update_submodules:
	@git submodule update --init

deps/python-irodsclient/irods: update_submodules

deps/six/six.py: update_submodules
