# generated Linux ccnx 3.10.0-123.8.1.el7.x86_64 #1 SMP Mon Sep 22 19:06:58 UTC 2014
#
#
#
SHEXT=so
SHLIBNAME=libccn.$(SHEXT).1
SHLIBDEPS=
SHARED_LD_FLAGS = -shared --whole-archive -soname=$(SHLIBNAME) -lc
PLATCFLAGS=-fPIC
CWARNFLAGS = -Wall -Wpointer-arith -Wreturn-type -Wstrict-prototypes
CPREFLAGS= -D_REENTRANT
COPT = -g
INSTALL_BASE = /usr/local
INSTALL_INCLUDE = $(INSTALL_BASE)/include
INSTALL_LIB = $(INSTALL_BASE)/lib
INSTALL_BIN = $(INSTALL_BASE)/bin
PCAP_PROGRAMS = ccndumppcap
RESOLV_LIBS = -lresolv
ANT = /usr/bin/ant
CP = cp
INSTALL = install
LS = /bin/ls
RM = rm -f
SH = /bin/sh
MKDEP = gcc -MM
BUILD_JAVA = true
DINST_BIN = $(DESTDIR)$(INSTALL_BIN)
DINST_INC = $(DESTDIR)$(INSTALL_INCLUDE)
DINST_LIB = $(DESTDIR)$(INSTALL_LIB)
