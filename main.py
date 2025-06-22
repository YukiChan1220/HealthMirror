from display.tm1637 import TM1637
from ecg.bmd101 import BMD101

def main():
    tm1637 = TM1637(9, 10)
    bmd101 = BMD101("/dev/ttyS0")
    print("Initialized.")
    tm1637.display([6,6,6,6])

    while True:
        ret, heart_rate, raw_data = bmd101.read_data()
        if ret != -1:
            a = -1;
            b = heart_rate // 100
            c = heart_rate // 10 % 10
            d = heart_rate % 10
            tm1637.display([a,b,c,d])
            print("Heart rate:", heart_rate)
        else:
            tm1637.display([9,9,9,9])
            print("Error")
    

if __name__ == "__main__":
    main()

