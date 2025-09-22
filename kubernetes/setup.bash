
# install docker
# Add Docker's official GPG key:
sudo apt-get update
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update

sudo apt-get -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# kubernetes
sudo apt-get install -y apt-transport-https ca-certificates curl gpg
sudo mkdir -p -m 755 /etc/apt/keyrings
curl -fsSL https://packages.k8s.io/core:/stable:/v1.32/deb/Release.key | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.32/deb/ /' | sudo tee /etc/apt/sources.list.d/kubernetes.list
sudo apt-get update
sudo apt-get install -y kubelet kubeadm kubectl
sudo swapoff -a

# --- NFS (server on master, client on workers) ---
set -euo pipefail

# Defaults if not provided via env
: "${MASTER_PREFIX:=master}"
: "${WORKER_PREFIX:=worker}"
: "${NFS_SERVER_IP:=10.10.0.2}"
: "${NFS_EXPORT:=/cluster-nfs}"
: "${NFS_SUBNET:=*}"

sudo apt-get update
sudo apt-get install -y nfs-kernel-server nfs-common

sudo mkdir -p "${NFS_EXPORT}"

HOSTNAME_LOWER=$(hostname | tr '[:upper:]' '[:lower:]')
if echo "${HOSTNAME_LOWER}" | grep -q "^$(echo "${MASTER_PREFIX}" | tr '[:upper:]' '[:lower:]')"; then
  # Configure as NFS server on master
  EXPORT_LINE="${NFS_EXPORT} ${NFS_SUBNET}(rw,sync,no_subtree_check,no_root_squash)"
  if ! grep -qs "^${NFS_EXPORT} " /etc/exports; then
    echo "${EXPORT_LINE}" | sudo tee -a /etc/exports >/dev/null
  fi
  sudo systemctl enable --now nfs-server || sudo systemctl enable --now nfs-kernel-server
  sudo exportfs -ra
else
  sudo mount -t nfs "${NFS_SERVER_IP}:${NFS_EXPORT}" "${NFS_EXPORT}"
fi

# ----- end of NFS -----

# kubernetes setup 
if echo "${HOSTNAME_LOWER}" | grep -q "^$(echo "${MASTER_PREFIX}" | tr '[:upper:]' '[:lower:]')"; then
  # Master node setup
  sudo kubeadm init --pod-network-cidr=10.244.0.0/16 
  mkdir -p $HOME/.kube
  sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
  sudo chown $(id -u):$(id -g) $HOME/.kube/config
  sudo kubeadm token create --print-join-command > /cluster-nfs/join.sh
  sudo chmod +x /cluster-nfs/join.sh
else 
  # Worker node setup
  if [ -f /cluster-nfs/join.sh ]; then
    sudo bash /cluster-nfs/join.sh
  else
    echo "Join script not found! Make sure the master node is set up first."
    exit 1
  fi
fi


