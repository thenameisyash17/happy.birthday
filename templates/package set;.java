package set;
import java.util.TreeSet;
public class Treest{
public static void main(String args[]){
    TreeSet t= new TreeSet();
    t.add("a");
    t.add("b");
    t.add("f");
    t.add("Y");
    t.add("d");
    t.add("j");
    System.out.println(t);
    System.out.println("first value"+t.first());
    System.out.println("lastvalue"+t.last());
    System.out.println("head values"+t.headSet("y"));
    System.out.println("head values"+t.headSet("d"));
    System.out.println("head values"+t.headSet("f"));
    System.out.println("head values"+t.subSet("a","f"));
}
}