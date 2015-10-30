/*
 * Based on the ccngetfile and ccnputfile methods developed by CCNx.
 */

package org.ccnx.ccn.utils;

import java.io.IOException;
import java.util.ArrayList;
import java.util.SortedSet;
import java.util.TreeSet;
import java.util.logging.Level;
import org.ccnx.ccn.CCNHandle;
import org.ccnx.ccn.impl.support.Log;
import org.ccnx.ccn.io.CCNFileInputStream;
import org.ccnx.ccn.io.CCNInputStream;
import org.ccnx.ccn.io.CCNOutputStream;
import org.ccnx.ccn.io.RepositoryFileOutputStream;
import org.ccnx.ccn.io.RepositoryOutputStream;
import org.ccnx.ccn.profiles.nameenum.BasicNameEnumeratorListener;
import org.ccnx.ccn.profiles.nameenum.CCNNameEnumerator;
import org.ccnx.ccn.protocol.ContentName;
import org.ccnx.ccn.protocol.MalformedContentNameStringException;

/**
 * Method to store on the repository of a CCNx router by requesting the 
 * files from the network.
 * @author Vitor
 */
public class ccnpopulaterepo implements Usage, BasicNameEnumeratorListener{
    private final String[] okArgs = {"-unversioned", "-v", "-timeout"};
    
    private boolean enumerate = false;
    private boolean verify = false;
    private boolean localVerify = false;
    private boolean hasData = false;
    private boolean timedOut = false;
    private int repositories = 1;
    private int answers = 0;
    
    private SortedSet<ContentName> allNames;
    private SortedSet<ContentName> download;
    
    private SortedSet<ContentName> localPrefixes;
    private ArrayList<ContentName> localFiles;
    private ArrayList<String> versions;
    
    private CCNHandle handle;
    private CCNNameEnumerator ccnNE;
    
    private ArrayList<String> wrongNames = null;

    public ccnpopulaterepo() { }    
    
    private void init(String[] args, ccnpopulaterepo ccnpopulaterepo){
        Log.setDefaultLevel(Level.WARNING);
        
        try {
            handle = CCNHandle.open();
        } catch (Exception e) {
            System.out.println("Exception while opening handler: " + e.getMessage());
            e.printStackTrace();
            System.exit(1);
        }
        
        CommonParameters.timeout = (long) 500;
        
        for (int i = 0; i < args.length; i++){
            if (args[i].equals("-e")){
                enumerate = true;
                CommonParameters.startArg++;
                continue;
            }
            if (args[i].equals("-verify")){
                verify = true;
                CommonParameters.startArg++;
                continue;
            }
            if (args[i].equals("-rep")){
                try{
                    repositories = Integer.parseInt(args[i+1]);
                } catch (NumberFormatException nfe){
                    usage(CommonArguments.getExtraUsage());
                }
                CommonParameters.startArg+=2;
                i++;
                continue;
            }
            if (!CommonArguments.parseArguments(args, i, ccnpopulaterepo, okArgs)){
                
                if (args[i].startsWith("ccnx")){
                    CommonParameters.startArg = i;
                    break;
                }
                usage(CommonArguments.getExtraUsage());
            }
            i = CommonParameters.startArg;
        }
        
        if (args.length == 1)
            usage(CommonArguments.getExtraUsage());
        
        if (!args[CommonParameters.startArg].startsWith("ccnx")){
            usage(CommonArguments.getExtraUsage());
        }
        
        if (CommonParameters.timeout < 1)
            CommonParameters.timeout = (long) 500;
        
        if (enumerate || verify)            
            ccnNE = new CCNNameEnumerator(handle, this);
        
        if (enumerate){
            allNames = new TreeSet<ContentName>();
            download = new TreeSet<ContentName>();
        }
        
        if (verify){
            localPrefixes = new TreeSet<ContentName>();
            localFiles = new ArrayList<ContentName>();
            versions = new ArrayList<String>();
        }
    }
    
    private synchronized void verifyLocal(){
        
        if (CommonParameters.verbose)
            System.out.println("Starting local verification");
        
        ContentName name;
        while(true){
            if (localPrefixes.isEmpty())
                break;
            name = localPrefixes.first();
            localPrefixes.remove(name);

            this.hasData = false;
            this.answers = 0;
            this.timedOut = false;
                                    
            try {
                ccnNE.registerPrefix(name,1,2); // local scope, generate new content
                
                long endTime = System.currentTimeMillis() + CommonParameters.timeout;
                while(!this.hasData && !timedOut){
                    this.wait(CommonParameters.timeout);

                    if (System.currentTimeMillis() >= endTime){
                        timedOut = true;
                    }
                }       
                
                ccnNE.cancelPrefix(name);
            } catch (Exception e){
                System.out.println("Error with prefix: " +name.toURIString());
                try{
                    ccnNE.cancelPrefix(name);
                } catch (Exception ex) {}     
                if (wrongNames != null)
                    wrongNames.add(name.toURIString());
            }
        }
        
        if (CommonParameters.verbose)
            System.out.println("Ending local verification");
    }
    
    private synchronized void processPrefixes(){
        
        if (CommonParameters.verbose)
            System.out.println("Starting Enumeration");
        
        ContentName name;
        while(true){
            if (allNames.isEmpty())
                break;
            name = allNames.first();
            allNames.remove(name);


            this.hasData = false;
            this.answers = 0;
            this.timedOut = false;
                        
            try {
                ccnNE.registerPrefix(name,-1,2); // any source, generate new content
                
                long endTime = System.currentTimeMillis() + CommonParameters.timeout;
                while(!(this.hasData && answers >= repositories) && !timedOut){
                    this.wait(CommonParameters.timeout);

                    if (System.currentTimeMillis() >= endTime){
                        timedOut = true;
                    }
                }        
                
                ccnNE.cancelPrefix(name);
            } catch (Exception e){
                System.out.println("Error with prefix: " +name.toURIString());
                try{
                    ccnNE.cancelPrefix(name);
                } catch (Exception ex) {}
                if (wrongNames != null)
                    wrongNames.add(name.toURIString());
            }
        }
        
        if (CommonParameters.verbose)
            System.out.println("Ending Enumeration");
        
        for (ContentName c : download){
            write(c);
        }
    }
    
    private void processNames(String[] args){
        ContentName name;
        
        if(enumerate){
            for (int i = CommonParameters.startArg; i < args.length; i++){
                try {
                    if (args[i].equals("/"))
                        name = ContentName.ROOT;
                    else
                        name = ContentName.fromURI(args[i]);
                } catch (MalformedContentNameStringException e){
                    System.out.println("Could not parse name: " +args[i]);
                    if (wrongNames != null)
                        wrongNames.add(args[i]);
                    continue;
                }
                allNames.add(name);
                if (verify)
                    localPrefixes.add(name);
            }
            if (verify){
                localVerify = true;
                verifyLocal();
                localVerify = false;
            }
            processPrefixes();
        }
        else{
            for (int i = CommonParameters.startArg; i < args.length; i++){
                try {
                    name = ContentName.fromURI(args[i]);
                } catch (MalformedContentNameStringException e){
                    System.out.println("Could not parse name: " +args[i]);
                    if (wrongNames != null)
                        wrongNames.add(args[i]);
                    continue;
                }
                if (verify){
                    localPrefixes.add(name);
                    localVerify = true;
                    verifyLocal();
                    localVerify = false;
                }
                write(name);
            }
        }        
    }
    
    private void write(ContentName argName){  
        CCNInputStream input = null;
        CCNOutputStream output = null;
        
        try {
            int size = 1024;
            long starttime = System.currentTimeMillis();

            if (CommonParameters.unversioned)
                input = new CCNInputStream(argName, handle);
            else
                input = new CCNFileInputStream(argName, handle);

            if (CommonParameters.unversioned)
                output = new RepositoryOutputStream(argName, handle);
            else
                output = new RepositoryFileOutputStream(argName, handle);

            int readcount;
            byte [] buffer = new byte[size];

            while ((readcount = input.read(buffer, 0, size)) != -1){
                output.write(buffer, 0, readcount);
            }
            
            input.close();
            output.close();
            System.out.println("Added file " +argName.toURIString() +" to the local repository");

            if (CommonParameters.verbose)
                System.out.println("ccnpopulaterepo took: " +(System.currentTimeMillis() - starttime) +"ms to add the file " +argName.toURIString() +" to the repository");

        } catch (IOException e) {
            System.out.println("Cannot populate repository with the file " +argName.toURIString());
            if (wrongNames != null)
                    wrongNames.add(argName.toURIString());
            try{
                if (input != null)
                    input.close();
                if (output != null)
                    output.close();
            } catch (Exception ex){                
            }
        }
    }
    
    @Override
    public void usage(String extraUsage){
        System.out.println("usage: ccnpopulaterepo " + extraUsage + "[-unversioned] [-v] [-e] [-verify] [-rep <number of repositories>] [-timeout millis (default is 500ms)] <ccnname> <ccnname,...>");
        System.exit(1);
    }
    
    public static void main(String[] args) {
        
        ccnpopulaterepo ccnpopulaterepo;
        ccnpopulaterepo = new ccnpopulaterepo();
        
        ccnpopulaterepo.init(args, ccnpopulaterepo);
        ccnpopulaterepo.processNames(args);
        
        System.exit(0);
    }

    @Override
    public synchronized int handleNameEnumerator(ContentName prefix, ArrayList<ContentName> names) {
        String name;
        if (localVerify){
            if (CommonParameters.verbose)
                System.out.println("Local Enumeration");

            for (int i = names.size()-1; i >= 0; i--){
                name = names.get(i).toString().replaceFirst("/", "");
                if (name.startsWith("=")){
                    if (CommonParameters.unversioned){
                        if (!localFiles.contains(prefix))
                            localFiles.add(prefix);
                    }
                    else{
                        if (!localFiles.contains(prefix)){
                            localFiles.add(prefix);
                            versions.add(name);
                        }
                        else{
                            if (Long.parseLong(versions.get(localFiles.indexOf(prefix)).replaceFirst("=FD", ""),16) < Long.parseLong(name.replaceFirst("=FD", ""), 16)){
                                versions.remove(localFiles.indexOf(prefix));
                                versions.add(localFiles.indexOf(prefix), name);
                            }
                        }
                    }
                }
                else{
                    if (!localPrefixes.contains(prefix.append(names.get(i))))
                        localPrefixes.add(prefix.append(names.get(i)));
                }
            }
        }
        else{
            if (CommonParameters.verbose)
                System.out.println("Global Enumeration");

            for (int i = names.size()-1; i >= 0; i--){
                name = names.get(i).toString().replaceFirst("/", "");
                if (name.startsWith("=")){
                    if (verify){
                        if (!CommonParameters.unversioned){
                            if (localFiles.contains(prefix)){
                                if (Long.parseLong(versions.get(localFiles.indexOf(prefix)).replaceFirst("=FD",""),16) >= Long.parseLong(name.replaceFirst("=FD",""),16))
                                    continue;
                            }
                        }
                    }
                    download.add(prefix);
                }
                else {
                    if (!allNames.contains(prefix.append(names.get(i))))
                        allNames.add(prefix.append(names.get(i)));
                }
            }
        }
                               
        this.hasData = true;
        this.answers++;
        this.notifyAll();
        
        return 0;
    }
    
    public ArrayList<String> process(String[] names){
        return process(names, false, false, false, 1, -1);
    }
    
    public ArrayList<String> process(String[] names, boolean unversioned){
        return process(names, unversioned, false, false, 1, -1);
    }
    
    public ArrayList<String> process(String[] names, boolean unversioned, int timeout){
        return process(names, unversioned, false, false, 1, timeout);
    }
    
    public ArrayList<String> process(boolean enumerate, String[] names){
        return process(names, false, enumerate, false, 1, -1);
    }
    
    public ArrayList<String> process(boolean enumerate, String[] names, int timeout){
        return process(names, false, enumerate, false, 1, timeout);
    }
    
    public ArrayList<String> process(String[] names, boolean unversioned, boolean enumerate, boolean verify, int repositories, int timeout){
        Log.setDefaultLevel(Level.SEVERE);
        
        try {
            handle = CCNHandle.open();
        } catch (Exception e) {
            System.out.println("Exception while opening handler: " + e.getMessage());
            return null;
        }
        
        if (enumerate || verify)            
            ccnNE = new CCNNameEnumerator(handle, this);
        
        if (enumerate){
            allNames = new TreeSet<ContentName>();
            download = new TreeSet<ContentName>();
        }        
        
        if (verify){
            localPrefixes = new TreeSet<ContentName>();
            localFiles = new ArrayList<ContentName>();
            versions = new ArrayList<String>();
        }
        
        wrongNames = new ArrayList<String>();
        
        CommonParameters.unversioned = unversioned;
        CommonParameters.timeout = (long) (timeout < 1 ? 500 : timeout);
        this.enumerate = enumerate;
        this.verify = verify;
        this.repositories = repositories;
        
        processNames(names);
                
        handle.closeAll();
        
        return wrongNames;
    }
}
