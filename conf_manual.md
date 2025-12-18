# HealthMirror Production Manual  
## 0 Material list  
| Material | Quantity    |  
| ------------------ | ----------- |  
| OrangePi 5B       | 1 |  
| TF Card (64GB)    | 1 |  
| RGB+IR Webcam     | 1 |  
| USB keyboard      | 1 |
| Peripheral board  | 1 |
| Bluetooth module  | 1 |
| 4-digit display   | 1 |
| BMD101 module     | 1 |
| Type-C power adapter 5V4A | 1 |
| Monitor with HDMI cable   | 1 |

## 1 System Setup
### 1.1 System install
- Download and install balenaEtcher [here](https://www.balena.io/etcher/).  
- Download the system image file [TODO]().  
- Insert the TF card to the computer.
- Use balenaEtcher to download the system image into the TF card.

### 1.2 Setup
- Insert the TF card into the OrangePi.
- Connect the monitor, the USB keyboard and the power adapter to the orangepi.
- Wait for system boot.
- Input the command below to connect to the internet (Tsinghua-Secure):
  ```bash
  nmcli connection edit type wifi con-name Tsinghua-Secure
  set 802-11-wireless.ssid Tsinghua-Secure
  set 802-11-wireless-security.key-mgmt wpa-eap 
  set 802-1x.eap peap
  set 802-1x.identity your_username
  set 802-1x.password your_password
  set 802-1x.phase2-auth mschapv2
  set ipv4.method auto
  set ipv6.method auto
  save
  yes
  quit
  nmcli connection up Tsinghua-Secure ifname wlan0
  ```
  You should see `Connection successfully activated`.
  Input `ifconfig` to show the IP address.

- Download PuTTY [TODO]() and FileZilla [TODO]().
- Use PuTTY to establish SSH connect to the OrangePi. Login with username `root`, password `orangepi`.

### 1.3 Configuration
- Network Firewall configure.
  ```bash
  apt install ufw
  sudo ufw default deny incoming
  sudo ufw default allow outgoing
  sudo ufw allow ssh 
  sudo ufw deny 5555 
  sudo ufw deny 23  
  sudo ufw enable
  sudo ufw status verbose
  ```

- Fix apt-get problem.
  ```bash  
  apt-get clean  
  cd /var/lib/apt  
  rm -rf lists.old  
  mv lists lists.old  
  mkdir -p lists/partial  
  apt-get clean  
  apt-get update  
  ```  

- Enable SSH key login
  **On Windows:**
  ```bash
  ssh-keygen -t ed25519 -C "windows-devboard-key"
  ```
  Open `C:\Users\<UserName>\.ssh\id_ed25519.pub`
  **On OrangePi:**
  ```bash
  mkdir -p ~/.ssh
  chmod 700 ~/.ssh
  nano ~/.ssh/authorized_keys
  ```
  Paste the content of `C:\Users\<UserName>\.ssh\id_ed25519.pub`.
  Ctrl+X to save and exit.
  ```bash
  chmod 600 ~/.ssh/authorized_keys
  ```
  ```bash
  nano /etc/ssh/sshd_config.d/my_ssh_conf.conf
  ```
  Paste:
  ```txt
  PasswordAuthentication no
  ChallengeResponseAuthentication no
  UsePAM no
  PubkeyAuthentication yes
  PermitRootLogin yes
  ```
  Run:
  ```bash
  sudo systemctl restart ssh
  ```

- Install Python 3.9. 
  ```bash  
  apt install python3.9  
  ```
  ```bash
  update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.9 1  
  update-alternatives --config python3  
  ```  

- Install pip and change download source  
  ```bash  
  apt install python3-pip  
  ```
  ```bash
  mkdir -p ~/.pip  
  nano ~/.pip/pip.conf  
  ```  
  Add the following content to `pip.conf`:  
  ```
  [global]
  index-url = https://pypi.tuna.tsinghua.edu.cn/simple
  ```  
  Use `Ctrl+X`, then `Y`, then `Enter` to save.

- Setup Virtual Environment
  ```bash  
  apt-get install python3.9-venv  
  ```
  ```bash
  cd ~  
  mkdir PythonVENV 
  cd PythonVENV   
  python3 -m venv healthmirror
  source healthmirror/bin/activate  
  ```  

- OpenCV library setup
  ```bash  
  pip install opencv-python  
  ```  
  Fix `libGL` issue:  
  ```bash  
  apt install libgl1-mesa-glx ffmpeg  
  ```  

- Libraries setup
  ```bash  
  pip install keyboard numpy==1.26.4 pillow mediapipe onnxruntime pandas paramiko pyserial smbus2  
  ```  

- Serial port configuration  
  ```bash  
  nano /boot/orangepiEnv.txt  
  ```  
  Add or modify the following line:  
  ```
  overlays=uart0-m2 uart1-m1 uart3-m0
  ```  
  Use `Ctrl+X`, then `Y`, then `Enter` to save.

- Reboot device. Re-login as `root`.

- wiringOP configuration
  ```bash  
  apt install git swig python3.9-dev python3-setuptools 
  ```
  ```bash 
  git clone --recursive https://github.com/orangepi-xunlong/wiringOP-Python -b next  
  cd wiringOP-Python  
  cd /usr/src/wiringOP-Python
  pip install setuptools 
  python generate-bindings.py > bindings.i  
  python setup.py install  
  ```  

- python decoding configuration 
  ```bash
  export PYTHONIOENCODING=utf-8 >> ~/.bashrc
  source ~/.bashrc
  ```

- System service configuration
  Copy `healthmirror.service` to `/etc/systemd/system/healthmirror.service`.
  Enable the service:
  ```bash
  sudo systemctl daemon-reload
  sudo systemctl restart healthmirror.service
  sudo systemctl enable healthmirror.service
  ```
  Enable real-time log output:
  ```bash
  sudo journalctl -u healthmirror.service -f
  ```

- Auto reboot configuration
  ```bash
  sudo crontab -e
  0 3 * * * /sbin/shutdown -r +1 "Will reboot in 1 minute"
  ```
  Add below in the file:
  ```bash
  0 3 * * * /sbin/shutdown -r now
  ```

- GitHub SSH configuration
  Github configuration
  ```
  git config --global user.name SongqinCheng
  git config --global user.email csq24@mails.tsinghua.edu.cn
  ```
  Generate new ssh key
  ```bash
  ssh-keygen -t rsa -b 4096 -C "2140499180@qq.com"
  ```
  Copy the output of:
  ```bash
  cat ~/.ssh/id_rsa.pub
  ```
  And paste into `ssh and gpg keys` in github.
  Modify remote github address:
  ```bash
  git remote set-url origin git@github.com:YukiChan1220/HealthMirror.git
  ```
  Clone repository:
  ```bash
  git clone git@github.com:YukiChan1220/HealthMirror
  ```

  - Peripherals configuration
  ```bash
  sudo orangepi-config
  ```
  system->hardware
  open uart0-m2, uart3-m2, uart4-m0, i2c4-m3, 

