/*
 * Based on the ccngetfile method developed by CCNx.
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
import org.ccnx.ccn.profiles.nameenum.BasicNameEnumeratorListener;
import org.ccnx.ccn.profiles.nameenum.CCNNameEnumerator;
import org.ccnx.ccn.protocol.ContentName;
import org.ccnx.ccn.protocol.MalformedContentNameStringException;

/**
 * Method to populate the Content Store of a CCNx router without storing the file(s).
 * @author Vitor
 */
public class ccnpopulatecache implements Usage, BasicNameEnumeratorListener {
    private final String[] okArgs = {"-unversioned", "-v", "-timeout"};
    private boolean enumerate = false;
    private SortedSet<ContentName> allNames;
    private SortedSet<ContentName> download;
    private CCNHandle handle;
    private CCNNameEnumerator ccnNE;
    private ArrayList<String> wrongNames;
    private boolean hasData;
    private boolean timedOut;
    
    private void init(String[] args, ccnpopulatecache ccnpopulatecache){
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
            if (!CommonArguments.parseArguments(args, i, ccnpopulatecache, okArgs)){
                
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
        
        if (enumerate){
            ccnNE = new CCNNameEnumerator(handle, this);
            allNames = new TreeSet<ContentName>();
            download = new TreeSet<ContentName>();
        }
    }
    
    private synchronized void processPrefixes(){
        ContentName name;
        while(true){
            if (allNames.isEmpty())
                break;
            name = allNames.first();
            allNames.remove(name);
            
            this.hasData = false;
            this.timedOut = false;
                        
            try {
                ccnNE.registerPrefix(name);
                
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
                wrongNames.add(name.toURIString());
            }
        }
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
                    wrongNames.add(args[i]);
                    continue;
                }
                allNames.add(name);
            }
            processPrefixes();
        }
        else{
            for (int i = CommonParameters.startArg; i < args.length; i++){
                try {
                    name = ContentName.fromURI(args[i]);
                } catch (MalformedContentNameStringException e){
                    System.out.println("Could not parse name: " +args[i]);
                    wrongNames.add(args[i]);
                    continue;
                }
                write(name);
            }
        }        
    }
    
    private void write(ContentName argName){    
        CCNInputStream input = null; 
        try {
            int size = 1024;
            long starttime = System.currentTimeMillis();

            if (CommonParameters.unversioned)
                input = new CCNInputStream(argName, handle);
            else
                input = new CCNFileInputStream(argName, handle);

            byte [] buffer = new byte[size];

            while (input.read(buffer) != -1);
            
            System.out.println("Added file " +argName.toURIString() +" to the local cache");

            if (CommonParameters.verbose)
                System.out.println("ccnpopulatecache took: " +(System.currentTimeMillis() - starttime) +"ms to add the file " +argName.toURIString() +" to the cache");

        } catch (IOException e) {
            System.out.println("Cannot populate cache with the file " +argName.toURIString());
            wrongNames.add(argName.toURIString());
            try{
                if (input != null)
                    input.close();
            } catch (Exception ex){                
            }
        }
    }
    
    @Override
    public void usage(String extraUsage){
        System.out.println("usage: ccnpopulatecache " + extraUsage + "[-unversioned] [-v] [-e] [-timeout millis (default is 500ms)] <ccnname> <ccnname,...>");
        System.exit(1);
    }
    
    public static void main(String[] args) {
        
        ccnpopulatecache ccnpopulatecache;
        ccnpopulatecache = new ccnpopulatecache();
        
        ccnpopulatecache.init(args, ccnpopulatecache);
        ccnpopulatecache.processNames(args);
        
        System.exit(0);
    }

    @Override
    public synchronized int handleNameEnumerator(ContentName prefix, ArrayList<ContentName> names) {
        String name;
        
        for (ContentName c : names){
            name = c.toString().replaceFirst("/", "");
            if (name.startsWith("=")){
                download.add(prefix);
            }
            else {
                if (!allNames.contains(prefix.append(c)))
                    allNames.add(prefix.append(c));
            }
        }      
        
        this.hasData = true;
        notifyAll();
        
        return 0;
    }
    
    public ArrayList<String> process(String[] names){
        return process(names, false, false, -1);
    }
    
    public ArrayList<String> process(String[] names, boolean unversioned){
        return process(names, unversioned, false, -1);
    }
    
    public ArrayList<String> process(String[] names, boolean unversioned, int timeout){
        return process(names, unversioned, false, timeout);
    }
    
    public ArrayList<String> process(boolean enumerate, String[] names){
        return process(names, false, enumerate, -1);
    }
    
    public ArrayList<String> process(boolean enumerate, String[] names, int timeout){
        return process(names, false, enumerate, timeout);
    }
    
    public ArrayList<String> process(String[] names, boolean unversioned, boolean enumerate, int timeout){       
        Log.setDefaultLevel(Level.SEVERE);
        
        try {
            handle = CCNHandle.open();
        } catch (Exception e) {
            System.out.println("Exception while opening handler: " + e.getMessage());
            return null;
        }
        
        if (enumerate){
            ccnNE = new CCNNameEnumerator(handle, this);
            allNames = new TreeSet<ContentName>();
            download = new TreeSet<ContentName>();
        }
        
        wrongNames = new ArrayList<String>();
        
        CommonParameters.unversioned = unversioned;
        CommonParameters.timeout = (long) (timeout < 1 ? 500 : timeout);
        this.enumerate = enumerate;
        
        processNames(names);
        
        handle.closeAll();
        
        return wrongNames;
    }
}