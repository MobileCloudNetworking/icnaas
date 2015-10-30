/**
 * @file ccnd_main.c
 *
 * A CCNx program.
 *
 * Copyright (C) 2009-2011, 2013 Palo Alto Research Center, Inc.
 *
 * This work is free software; you can redistribute it and/or modify it under
 * the terms of the GNU General Public License version 2 as published by the
 * Free Software Foundation.
 * This work is distributed in the hope that it will be useful, but WITHOUT ANY
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or
 * FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
 * for more details. You should have received a copy of the GNU General Public
 * License along with this program; if not, write to the
 * Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor,
 * Boston, MA 02110-1301, USA.
 */

#include <signal.h>
#include <stddef.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <openssl/evp.h>
#include <openssl/err.h>
#include <openssl/crypto.h>

#include <fcntl.h>

#include "ccnd_private.h"

static int
stdiologger(void *loggerdata, const char *format, va_list ap)
{
    FILE *fp = (FILE *)loggerdata;
    return(vfprintf(fp, format, ap));
}

int
main(int argc, char **argv)
{
    struct ccnd_handle *h;
    char *fmc_mon;

    if (argc > 1) {
        fprintf(stderr, "%s", ccnd_usage_message);
        exit(1);
    }
    signal(SIGPIPE, SIG_IGN);
    h = ccnd_create(argv[0], stdiologger, stderr);
    if (h == NULL)
        exit(1);

    fmc_mon = getenv("FMC_MONITORING");

    if (fmc_mon != NULL && strcmp(fmc_mon, "TRUE") == 0){

        h->logfile = open("/tmp/interest_monitoring.log", O_RDWR);
        if (h->logfile < 0){
            ccnd_msg(h, "failed to open named pipe");
            ccnd_msg(h, "creating new named pipe");

            h->logfile = mkfifo("/tmp/interest_monitoring.log", S_IRUSR | S_IWUSR | S_IRGRP | S_IWGRP | S_IROTH | S_IWOTH);
            if (h->logfile < 0){
                ccnd_msg(h, "failed to create named pipe");
                exit(1);
            }
            h->logfile = open("/tmp/interest_monitoring.log", O_RDWR);
        }
    } else {
        h->logfile = -1;
    }

    ccnd_run(h);

    if (h->logfile != -1)
        dprintf(h->logfile, "exit\n");

    ccnd_msg(h, "exiting.");

    if (h->logfile != -1)
        close(h->logfile);

    ccnd_destroy(&h);
    ERR_remove_state(0);
    EVP_cleanup();
    CRYPTO_cleanup_all_ex_data();
    exit(0);
}
