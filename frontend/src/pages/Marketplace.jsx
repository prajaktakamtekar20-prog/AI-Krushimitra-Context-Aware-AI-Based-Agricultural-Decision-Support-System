import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../context/LanguageContext'
import { farmerApi, marketplaceApi } from '../services/api'
import { translatePlantVillageCrop } from '../constants/crops'
import { localizeDisplayName } from '../translations/brand'
import { localizeLocation } from '../translations/locations'
import { localizeVariety } from '../translations/cropMarkets'
import { formatQuantity, localizeUnit } from '../translations/units'
import { CROP_IMAGE_FALLBACK, getCropImage, getCropImagePosition } from '../constants/cropImages'
import Background from '../components/Background'
import Navbar from '../components/Navbar'
import GlassCard from '../components/GlassCard'
import GradientButton from '../components/GradientButton'
import VirtualKeyboard from '../components/VirtualKeyboard'
import { VoiceInputButton } from '../components/VoiceControls'
import './Marketplace.css'

const categories = ['Vegetables', 'Grains', 'Fruits', 'Pulses', 'Other']
const units = ['kg', 'quintal', 'tonne']
const buyerTypes = ['Individual', 'Retailer', 'Wholesaler', 'Restaurant', 'Distributor', 'Other']
const defaultCropCategory = (crop) => {
  const name = String(crop || '').trim().toLowerCase()
  if (name === 'tomato') return 'Vegetables'
  if (name === 'maize' || name === 'corn' || name === 'corn (maize)' || name === 'wheat') return 'Grains'
  return 'Other'
}
const tomorrow = () => {
  const day = new Date()
  day.setDate(day.getDate() + 1)
  return day.toISOString().slice(0, 10)
}
const emptyRequirement = () => ({
  crop: '', category: 'Vegetables', quantity: '', unit: 'kg', expected_price_per_unit: '',
  delivery_location: '', delivery_date: tomorrow(), quality_preferences: '', description: ''
})
const emptyOffer = () => ({ quantity: '', price_per_unit: '', message: '', delivery_date: tomorrow() })
const emptyProduce = () => ({
  crop: '', category: 'Vegetables', quantity: '', unit: 'kg', price_per_unit: '', location: '', description: '', image_url: '',
  min_order_quantity: '', available_from: '', publish: true
})
const emptyListingOrder = (buyerProfile) => ({
  quantity: '',
  delivery_location: buyerProfile?.delivery_location || '',
  delivery_address: buyerProfile?.address || '',
  delivery_date: tomorrow(),
  message: '',
  idempotency_key: crypto.randomUUID()
})
const emptyFarmerOrderRequest = (buyerProfile, farmer = null) => ({
  crop: farmer?.listings?.[0]?.crop || farmer?.farming?.crop || '',
  quantity: '',
  unit: farmer?.listings?.[0]?.unit || 'kg',
  price_per_unit: farmer?.listings?.[0]?.price_per_unit || '',
  delivery_location: buyerProfile?.delivery_location || '',
  delivery_date: tomorrow(),
  message: '',
  listing_id: '',
  idempotency_key: crypto.randomUUID()
})
const defaultBuyer = (user) => ({
  full_name: user?.full_name || user?.name || '',
  business_name: '',
  buyer_type: 'Individual',
  crop_preferences: [],
  phone: user?.mobile || '',
  whatsapp: user?.mobile || '',
  email: user?.email || '',
  delivery_location: '',
  address: '',
  additional_info: ''
})
const errorMessage = (error, fallback = 'Something went wrong. Please try again.') => {
  const detail = error?.response?.data?.detail
  if (Array.isArray(detail)) return detail.map((item) => item.msg).join(' ')
  return typeof detail === 'string' ? detail : error?.message || fallback
}
const formatRupees = (amount) => `₹${Number(amount || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
const whatsappNumber = (value) => {
  const digits = String(value || '').replace(/\D/g, '')
  if (digits.length === 10) return `91${digits}`
  if (digits.length === 11 && digits.startsWith('0')) return `91${digits.slice(1)}`
  return digits
}
const chatDayLabel = (value) => {
  const date = new Date(value)
  const today = new Date()
  const yesterday = new Date()
  yesterday.setDate(today.getDate() - 1)
  const dayKey = (item) => `${item.getFullYear()}-${item.getMonth()}-${item.getDate()}`
  if (dayKey(date) === dayKey(today)) return 'Today'
  if (dayKey(date) === dayKey(yesterday)) return 'Yesterday'
  return date.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}
const chatTimeLabel = (value) => value ? new Date(value).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) : ''
const chatEmojis = ['😀', '😊', '😂', '❤️', '👍', '🙏', '🌾', '🌱', '👋', '✅', '✨', '🥰']

const Marketplace = () => {
  const { user, updateUserProfile } = useAuth()
  const { t, language, formatNumber, formatDate } = useLanguage()
  const mt = (key, values) => t(`marketplace.${key}`, values)
  const displayUnit = (unit) => localizeUnit(unit || 'kg', language)
  const displayQuantity = (value, unit) => formatQuantity(value, unit || 'kg', language, formatNumber)
  const orderStatusLabel = (status) => {
    const statusKeys = {
      pending: 'statusPending',
      accepted: 'statusAccepted',
      rejected: 'statusRejected',
      in_progress: 'statusInProgress',
      completed: 'statusCompleted',
      cancelled: 'statusCancelled'
    }
    return statusKeys[status] ? mt(statusKeys[status]) : String(status || '').replace('_', ' ')
  }
  const localizedCategories = categories.map((value) => ({ value, label: t(`dropdowns.categories.${value}`) }))
  const localizedUnits = units.map((value) => ({ value, label: t(`dropdowns.units.${value}`) }))
  const localizedBuyerTypes = buyerTypes.map((value) => ({ value, label: t(`dropdowns.buyerTypes.${value}`) }))
  const location = useLocation()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = location.pathname === '/profile'
    ? 'profile'
    : searchParams.get('tab') || (user?.role === 'buyer' ? 'produce' : 'myProduce')
  const [buyerProfile, setBuyerProfile] = useState(null)
  const [farmerProfile, setFarmerProfile] = useState(null)
  const [publicFarmer, setPublicFarmer] = useState(null)
  const [overview, setOverview] = useState(null)
  const [farmers, setFarmers] = useState([])
  const [farmerFilters, setFarmerFilters] = useState({ name: '', location: '', crop: '' })
  const [notifications, setNotifications] = useState([])
  const [produce, setProduce] = useState([])
  const [requirements, setRequirements] = useState([])
  const [orders, setOrders] = useState([])
  const [orderDetails, setOrderDetails] = useState({})
  const [requirementOffers, setRequirementOffers] = useState({})
  const [buyerForm, setBuyerForm] = useState(() => defaultBuyer(user))
  const [requirementForm, setRequirementForm] = useState(emptyRequirement)
  const [produceForm, setProduceForm] = useState(emptyProduce)
  const [produceFormError, setProduceFormError] = useState('')
  const [offerForm, setOfferForm] = useState(emptyOffer)
  const [editingRequirement, setEditingRequirement] = useState('')
  const [editingProduce, setEditingProduce] = useState('')
  const [editingProfileCrop, setEditingProfileCrop] = useState(false)
  const [offeringRequirement, setOfferingRequirement] = useState('')
  const [selectedProduce, setSelectedProduce] = useState(null)
  const [orderingListing, setOrderingListing] = useState(null)
  const [listingOrderForm, setListingOrderForm] = useState(() => emptyListingOrder(null))
  const [requestingFarmerOrder, setRequestingFarmerOrder] = useState(false)
  const [farmerOrderRequestForm, setFarmerOrderRequestForm] = useState(() => emptyFarmerOrderRequest(null))
  const [activeChatOrder, setActiveChatOrder] = useState(() => searchParams.get('orderId') || '')
  const [chatConversations, setChatConversations] = useState([])
  const [chatMessages, setChatMessages] = useState([])
  const [chatLoading, setChatLoading] = useState(false)
  const [chatLoadError, setChatLoadError] = useState('')
  const [chatText, setChatText] = useState('')
  const [chatSending, setChatSending] = useState(false)
  const [chatReply, setChatReply] = useState(null)
  const [emojiPickerOpen, setEmojiPickerOpen] = useState(false)
  const [chatActionMenu, setChatActionMenu] = useState('')
  const [chatSidebarOpen, setChatSidebarOpen] = useState(() => !searchParams.get('orderId'))
  const chatHistoryRef = useRef(null)
  const chatEndRef = useRef(null)
  const chatInputRef = useRef(null)
  const chatWasNearBottom = useRef(true)
  const chatSendLock = useRef(false)
  const [highlightedOrder, setHighlightedOrder] = useState('')
  const [filters, setFilters] = useState({ crop: '', location: '', category: '' })
  const [requirementFilters, setRequirementFilters] = useState({
    crop: '', location: '', min_quantity: '', max_quantity: '', min_price: '', max_price: ''
  })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [notice, setNotice] = useState(null)
  const [searchText, setSearchText] = useState('')
  const chatOrderIdFromUrl = searchParams.get('orderId') || ''

  const isBuyer = user?.role === 'buyer'
  const isFarmer = user?.role === 'farmer'
  const tabs = isBuyer
    ? [
      { id: 'marketplace', label: mt('title') },
      { id: 'produce', label: t('nav.browseProducts') },
      { id: 'orders', label: t('nav.myOrders') },
      { id: 'farmers', label: mt('directory') },
      { id: 'notifications', label: mt('notifications') },
      { id: 'messages', label: mt('messages') },
      { id: 'profile', label: `${mt('buyer')} ${t('nav.myProfile')}` }
      ]
    : [
      { id: 'myProduce', label: mt('myListings') },
      { id: 'orders', label: t('nav.myOrders') },
      { id: 'messages', label: mt('messages') },
      { id: 'profile', label: `${mt('farmer')} ${t('nav.myProfile')}` }
    ]

  const notify = (kind, text) => {
    setNotice({ kind, text })
    window.setTimeout(() => setNotice(null), 5000)
  }
  const navigateTab = (nextTab) => {
    if (nextTab === 'profile') {
      navigate('/profile')
      return
    }
    if (location.pathname === '/profile') {
      navigate(`/marketplace?tab=${nextTab}`)
    } else {
      setSearchParams(nextTab === 'marketplace' ? {} : { tab: nextTab })
    }
  }
  const openOrderChat = (orderId) => {
    setActiveChatOrder(orderId)
    setChatSidebarOpen(false)
    if (location.pathname === '/profile') {
      navigate(`/marketplace?tab=messages&orderId=${encodeURIComponent(orderId)}`)
    } else {
      setSearchParams({ tab: 'messages', orderId })
    }
  }

  const loadProfiles = useCallback(async () => {
    if (isBuyer) {
      try {
        const profile = await marketplaceApi.getBuyerProfile()
        setBuyerProfile(profile)
        setBuyerForm((current) => ({ ...defaultBuyer(user), ...profile }))
      } catch (error) {
        if (error.response?.status !== 404) throw error
        setBuyerProfile(null)
        setBuyerForm(defaultBuyer(user))
      }
      setFarmerProfile(null)
      return
    }
    try {
      setFarmerProfile(await farmerApi.getProfile())
    } catch (error) {
      if (error.response?.status !== 404) throw error
      setFarmerProfile(null)
    }
    setBuyerProfile(null)
  }, [isBuyer, user])

  useEffect(() => {
    const allowedTabs = isBuyer
      ? ['marketplace', 'produce', 'requirements', 'myRequirements', 'orders', 'farmers', 'farmerProfile', 'notifications', 'messages', 'profile', 'dashboard', 'postRequirement']
      : ['marketplace', 'produce', 'myProduce', 'requirements', 'incomingOrders', 'orders', 'messages', 'listProduce']
    if (user?.role && !allowedTabs.includes(tab)) {
      setSearchParams({ tab: isBuyer ? 'dashboard' : 'myProduce' }, { replace: true })
    }
  }, [isBuyer, setSearchParams, tab, user?.role])

  const loadTab = useCallback(async () => {
    setLoading(true)
    try {
      if (tab === 'marketplace' || tab === 'produce') {
        setProduce(await marketplaceApi.getProduce(filters))
      } else if (tab === 'requirements') {
        if (isFarmer) setRequirements(await marketplaceApi.getRequirements(requirementFilters))
        else if (isBuyer) setRequirements(await marketplaceApi.getRequirements({ mine: true }))
        else setRequirements([])
      } else if (tab === 'myRequirements') {
        setRequirements(await marketplaceApi.getRequirements({ mine: true }))
      } else if (tab === 'orders' || tab === 'incomingOrders') {
        const allOrders = await marketplaceApi.getOrders()
        const myOrders = tab === 'incomingOrders'
          ? allOrders.filter((order) => order.farmer_id === user?.id)
          : allOrders
        setOrders(myOrders)
        const details = await Promise.all(myOrders.map(async (order) => {
          try {
            return [order.id, await marketplaceApi.getOrder(order.id)]
          } catch (error) {
            console.error('Could not load order details:', error)
            return [order.id, null]
          }
        }))
        setOrderDetails(Object.fromEntries(details.filter(([, value]) => value)))
      } else if (tab === 'dashboard') {
        setOverview(await marketplaceApi.getDashboard())
      } else if (tab === 'myProduce') {
        setProduce(await marketplaceApi.getMyProduce())
      } else if (tab === 'farmers') {
        setFarmers(await marketplaceApi.getFarmers(farmerFilters))
      } else if (tab === 'farmerProfile') {
        const farmerId = searchParams.get('farmerId')
        if (!farmerId) {
          setPublicFarmer(null)
          navigateTab('farmers')
        } else {
          setPublicFarmer(await marketplaceApi.getPublicFarmerProfile(farmerId))
        }
      } else if (tab === 'notifications') {
        setNotifications(await marketplaceApi.getNotifications())
      } else if (tab === 'messages') {
        const chatOrders = await marketplaceApi.getConversations()
        setChatConversations(chatOrders)
        setOrders(chatOrders)
        const selectedOrderExists = chatOrders.some((order) => order.id === activeChatOrder)
        if (!selectedOrderExists && chatOrders.length) {
          const firstOrderId = chatOrders[0].id
          setActiveChatOrder(firstOrderId)
          setChatSidebarOpen(false)
          setSearchParams({ tab: 'messages', orderId: firstOrderId }, { replace: true })
        }
        if (!chatOrders.length) {
          setChatMessages([])
          setChatLoadError('')
          setActiveChatOrder('')
          setChatSidebarOpen(true)
          if (searchParams.has('orderId')) {
            setSearchParams({ tab: 'messages' }, { replace: true })
          }
        }
      }
    } catch (error) {
      if (tab === 'messages') setChatLoadError(errorMessage(error))
      notify('error', errorMessage(error))
    } finally {
      setLoading(false)
    }
  }, [tab, filters, requirementFilters, farmerFilters, isFarmer, isBuyer, user?.id, searchParams, activeChatOrder, setSearchParams])

  useEffect(() => {
    loadProfiles().catch((error) => notify('error', errorMessage(error)))
  }, [loadProfiles])
  useEffect(() => {
    loadTab()
  }, [loadTab])

  useEffect(() => {
    if (tab !== 'messages' || activeChatOrder === chatOrderIdFromUrl) return
    setActiveChatOrder(chatOrderIdFromUrl)
    setChatSidebarOpen(false)
    setChatMessages([])
    setChatText('')
    setEmojiPickerOpen(false)
    setChatLoadError('')
  }, [tab, chatOrderIdFromUrl, activeChatOrder])

  useEffect(() => {
    if (tab !== 'messages' || !activeChatOrder) return undefined
    let active = true
    let fetching = false
    chatWasNearBottom.current = true
    setChatLoading(true)
    setChatLoadError('')

    const fetchMessages = async () => {
      if (fetching) return
      fetching = true
      try {
        const latestMessages = await marketplaceApi.getOrderMessages(activeChatOrder)
        if (!active) return
        setChatMessages((current) => {
          const currentIds = new Set(current.map((message) => message.id))
          const hasNewMessages = latestMessages.some((message) => !currentIds.has(message.id))
          chatWasNearBottom.current = chatWasNearBottom.current || hasNewMessages
          return latestMessages
        })
        const latestConversations = await marketplaceApi.getConversations()
        if (!active) return
        setChatConversations(latestConversations)
        setOrders(latestConversations)
        setChatLoadError('')
      } catch (error) {
        if (active) setChatLoadError(errorMessage(error))
      } finally {
        fetching = false
        if (active) setChatLoading(false)
      }
    }

    setChatMessages([])
    fetchMessages()
    const interval = window.setInterval(() => {
      fetchMessages()
    }, 5000)
    return () => {
      active = false
      window.clearInterval(interval)
    }
  }, [tab, activeChatOrder])

  useEffect(() => {
    if (!chatWasNearBottom.current) return
    chatEndRef.current?.scrollIntoView({ block: 'end', behavior: 'smooth' })
  }, [chatMessages, activeChatOrder])

  const chooseTab = (nextTab) => {
    setSelectedProduce(null)
    setOfferingRequirement('')
    navigateTab(nextTab)
  }

  const submitBuyerProfile = async (event) => {
    event.preventDefault()
    setSaving(true)
    try {
      const saved = await marketplaceApi.saveBuyerProfile(buyerForm)
      setBuyerProfile(saved)
      updateUserProfile({
        ...user,
        ...saved,
        id: user?.id,
        user_id: user?.id,
        role: user?.role,
        mobile: user?.mobile || saved.phone,
        hasProfile: true,
        profile_complete: true
      })
      notify('success', 'Buyer profile saved.')
    } catch (error) {
      setProduceFormError(errorMessage(error, mt('error')))
    } finally {
      setSaving(false)
    }
  }

  const submitRequirement = async (event) => {
    event.preventDefault()
    setSaving(true)
    try {
      if (editingRequirement) {
        await marketplaceApi.updateRequirement(editingRequirement, requirementForm)
        notify('success', 'Requirement updated.')
      } else {
        const created = await marketplaceApi.createRequirement(requirementForm)
        notify('success', `Requirement posted. Reference: ${created.id}`)
      }
      setRequirementForm(emptyRequirement())
      setEditingRequirement('')
      navigateTab('myRequirements')
      await loadTab()
    } catch (error) {
      notify('error', errorMessage(error, mt('error')))
    } finally {
      setSaving(false)
    }
  }

  const submitProduce = async (event) => {
    event.preventDefault()
    setProduceFormError('')
    const quantity = Number(produceForm.quantity || 0)
    const price = Number(produceForm.price_per_unit || 0)
    const minimum = produceForm.min_order_quantity === '' ? null : Number(produceForm.min_order_quantity)
    if (produceForm.publish && (quantity <= 0 || price <= 0)) {
      setProduceFormError(mt('listingValidationPriceQuantity'))
      return
    }
    if (minimum !== null && (minimum <= 0 || (quantity > 0 && minimum > quantity))) {
      setProduceFormError(mt('listingValidationMinimum'))
      return
    }
    setSaving(true)
    try {
      const payload = {
        ...produceForm,
        quantity,
        price_per_unit: price,
        min_order_quantity: minimum,
        available_from: produceForm.available_from || null,
        publish: Boolean(produceForm.publish)
      }
      if (editingProduce) {
        await marketplaceApi.updateProduce(editingProduce, payload)
        notify('success', payload.publish ? mt('listingSavedPublished') : mt('draftSaved'))
      } else {
        await marketplaceApi.createProduce(payload)
        notify('success', payload.publish ? mt('produceListingPublished') : mt('draftSaved'))
      }
      setProduceForm(emptyProduce())
      setEditingProduce('')
      setEditingProfileCrop(false)
      setProduceFormError('')
      navigateTab('myProduce')
      await loadTab()
    } catch (error) {
      notify('error', errorMessage(error))
    } finally {
      setSaving(false)
    }
  }

  const submitOffer = async (event) => {
    event.preventDefault()
    setSaving(true)
    try {
      await marketplaceApi.submitOffer(offeringRequirement, offerForm)
      setOfferingRequirement('')
      setOfferForm(emptyOffer())
      notify('success', 'Your offer has been sent to the buyer.')
      await loadTab()
    } catch (error) {
      notify('error', errorMessage(error))
    } finally {
      setSaving(false)
    }
  }

  const openRequirementEditor = (requirement) => {
    setRequirementForm({
      crop: requirement.crop,
      category: requirement.category,
      quantity: requirement.quantity,
      unit: requirement.unit,
      expected_price_per_unit: requirement.expected_price_per_unit,
      delivery_location: requirement.delivery_location,
      delivery_date: requirement.delivery_date,
      quality_preferences: requirement.quality_preferences || '',
      description: requirement.description || ''
    })
    setEditingRequirement(requirement.id)
    navigateTab('postRequirement')
  }

  const cancelRequirement = async (requirement) => {
    if (!window.confirm(`Cancel the requirement for ${requirement.crop}?`)) return
    try {
      await marketplaceApi.cancelRequirement(requirement.id)
      notify('success', 'Requirement cancelled.')
      await loadTab()
    } catch (error) {
      notify('error', errorMessage(error))
    }
  }

  const showOffers = async (requirement) => {
    try {
      const rows = await marketplaceApi.getRequirementOffers(requirement.id)
      setRequirementOffers((current) => ({ ...current, [requirement.id]: rows }))
    } catch (error) {
      notify('error', errorMessage(error))
    }
  }

  const decideOffer = async (requirementId, offerId, decision) => {
    const action = decision === 'accept' ? 'accept this offer and create an order' : 'reject this offer'
    if (!window.confirm(`Are you sure you want to ${action}?`)) return
    try {
      await marketplaceApi.decideOffer(requirementId, offerId, decision)
      notify('success', decision === 'accept' ? 'Offer accepted. Your order is ready.' : 'Offer rejected.')
      await showOffers({ id: requirementId })
      await loadTab()
    } catch (error) {
      notify('error', errorMessage(error))
    }
  }

  const searchProducts = async (event) => {
    event.preventDefault()
    try {
      setLoading(true)
      setProduce(await marketplaceApi.getProduce({ ...filters, crop: searchText || filters.crop }))
    } catch (error) {
      notify('error', errorMessage(error))
    } finally {
      setLoading(false)
    }
  }

  const openListingOrder = (listing) => {
    setListingOrderForm(emptyListingOrder(buyerProfile))
    setOrderingListing(listing)
  }

  const editProduce = (listing) => {
    setProduceForm({
      crop: listing.crop,
      category: listing.category || defaultCropCategory(listing.crop),
      quantity: listing.quantity,
      unit: listing.unit,
      price_per_unit: listing.price_per_unit,
      location: listing.location,
      description: listing.description || '',
      image_url: listing.image_url || '',
      min_order_quantity: listing.min_order_quantity ?? '',
      available_from: listing.available_from || '',
      publish: listing.status === 'available'
    })
    setEditingProduce(listing.id)
    setEditingProfileCrop(Boolean(listing.profile_crop_key))
    setProduceFormError('')
  }

  const cancelProduceEdit = () => {
    setEditingProduce('')
    setEditingProfileCrop(false)
    setProduceForm(emptyProduce())
    setProduceFormError('')
  }

  const startNewProduce = () => {
    cancelProduceEdit()
    navigateTab('listProduce')
  }

  const saveProduceCard = async (listing) => {
    setProduceFormError('')
    const quantity = Number(produceForm.quantity || 0)
    const price = Number(produceForm.price_per_unit || 0)
    const minimum = produceForm.min_order_quantity === '' ? null : Number(produceForm.min_order_quantity)

    if (!Number.isFinite(price) || price < 0 || !Number.isFinite(quantity) || quantity < 0) {
      setProduceFormError('Enter a valid, non-negative price and available quantity.')
      return
    }
    if (produceForm.publish && (quantity <= 0 || price <= 0)) {
      setProduceFormError('Enter a price and available quantity greater than zero before publishing.')
      return
    }
    if (minimum !== null && (!Number.isFinite(minimum) || minimum <= 0 || (quantity > 0 && minimum > quantity))) {
      setProduceFormError('Minimum order must be positive and cannot exceed available quantity.')
      return
    }

    setSaving(true)
    const payload = {
      ...produceForm,
      quantity,
      price_per_unit: price,
      min_order_quantity: minimum,
      available_from: produceForm.available_from || null,
      publish: Boolean(produceForm.publish)
    }
    let updated
    try {
      updated = await marketplaceApi.updateProduce(listing.id, payload)
      setProduce((current) => current.map((item) => item.id === updated.id ? updated : item))
    } catch (error) {
      notify('error', errorMessage(error))
      setSaving(false)
      return
    }

    try {
      const refreshed = await marketplaceApi.getMyProduce()
      const persisted = refreshed.find((item) => item.id === listing.id)
      if (!persisted) throw new Error('The saved listing was not returned when My Listings was reloaded.')
      const persistedDate = persisted.available_from ? String(persisted.available_from).slice(0, 10) : ''
      if (
        Number(persisted.price_per_unit) !== price
        || Number(persisted.quantity) !== quantity
        || (persisted.min_order_quantity == null ? null : Number(persisted.min_order_quantity)) !== minimum
        || persistedDate !== (payload.available_from || '')
        || (persisted.description || '') !== (payload.description || '')
        || persisted.status !== (payload.publish ? 'available' : 'draft')
      ) {
        throw new Error('The reloaded listing does not contain all the saved values.')
      }
      setProduce(refreshed)
      cancelProduceEdit()
      notify('success', persisted.status === 'available' ? 'Listing saved and published.' : 'Draft saved.')
    } catch (error) {
      notify('error', `Listing was saved, but could not be verified after reloading: ${errorMessage(error)}`)
    } finally {
      setSaving(false)
    }
  }

  const removeProduce = async (listing) => {
    if (!window.confirm(`Delete your ${listing.crop} listing? Existing order history will be preserved.`)) return
    try {
      await marketplaceApi.removeProduce(listing.id)
      setProduce((current) => current.filter((item) => item.id !== listing.id))
      if (editingProduce === listing.id) cancelProduceEdit()
      notify('success', 'Produce listing removed.')
    } catch (error) {
      notify('error', errorMessage(error))
    }
  }

  const submitListingOrder = async (event) => {
    event.preventDefault()
    if (!orderingListing) return
    setSaving(true)
    try {
      const created = await marketplaceApi.createListingOrder(orderingListing.id, {
        ...listingOrderForm,
        quantity: Number(listingOrderForm.quantity)
      })
      setOrderingListing(null)
      notify('success', `Order ${created.id} submitted. The farmer will review it shortly.`)
      navigateTab('orders')
    } catch (error) {
      notify('error', errorMessage(error))
    } finally {
      setSaving(false)
    }
  }

  const openFarmerOrderRequest = () => {
    if (!publicFarmer) return
    setFarmerOrderRequestForm(emptyFarmerOrderRequest(buyerProfile, publicFarmer))
    setRequestingFarmerOrder(true)
  }

  const updateFarmerOrderRequestListing = (listingId) => {
    const listing = publicFarmer?.listings?.find((item) => item.id === listingId)
    setFarmerOrderRequestForm((current) => ({
      ...current,
      listing_id: listingId,
      crop: listing?.crop || current.crop || publicFarmer?.farming?.crop || '',
      unit: listing?.unit || current.unit || 'kg',
      price_per_unit: listing?.price_per_unit ?? current.price_per_unit
    }))
  }

  const submitFarmerOrderRequest = async (event) => {
    event.preventDefault()
    if (!publicFarmer) return
    setSaving(true)
    try {
      const created = await marketplaceApi.createFarmerOrderRequest(publicFarmer.id, {
        ...farmerOrderRequestForm,
        quantity: Number(farmerOrderRequestForm.quantity),
        price_per_unit: Number(farmerOrderRequestForm.price_per_unit),
        listing_id: farmerOrderRequestForm.listing_id || null
      })
      setRequestingFarmerOrder(false)
      notify('success', `Order request ${created.id} submitted. The farmer will review it shortly.`)
      navigateTab('orders')
    } catch (error) {
      notify('error', errorMessage(error))
    } finally {
      setSaving(false)
    }
  }

  const decideListingOrder = async (order, decision) => {
    const action = decision === 'accept'
      ? 'accept this order'
      : order.order_type === 'farmer_request'
        ? 'reject this order request'
        : 'reject this order and return its reserved stock'
    if (!window.confirm(`Are you sure you want to ${action}?`)) return
    try {
      await marketplaceApi.decideListingOrder(order.id, decision)
      notify('success', decision === 'accept'
        ? 'Order accepted.'
        : order.order_type === 'farmer_request'
          ? 'Order request rejected.'
          : 'Order rejected and listing stock restored.')
      await loadTab()
    } catch (error) {
      notify('error', errorMessage(error))
    }
  }

  const cancelListingOrder = async (order) => {
    const confirmation = order.order_type === 'farmer_request' && !order.listing_id
      ? 'Cancel this pending order request?'
      : 'Cancel this pending order? Its reserved quantity will return to the listing.'
    if (!window.confirm(confirmation)) return
    try {
      await marketplaceApi.cancelListingOrder(order.id)
      notify('success', order.order_type === 'farmer_request' && !order.listing_id
        ? 'Order request cancelled.'
        : 'Order cancelled and listing stock restored.')
      await loadTab()
    } catch (error) {
      notify('error', errorMessage(error))
    }
  }

  const estimatedBudget = useMemo(
    () => Number(requirementForm.quantity || 0) * Number(requirementForm.expected_price_per_unit || 0),
    [requirementForm.quantity, requirementForm.expected_price_per_unit]
  )

  const renderBuyerProfile = () => (
    <GlassCard className="mp-form-card">
      <div className="mp-section-heading">
        <div>
          <span className="mp-eyebrow">{mt('identity')}</span>
              <h2>{buyerProfile ? mt('editBuyerProfile') : mt('createBuyerProfile')}</h2>
              <p>{mt('profilePrivate')}</p>
        </div>
      </div>
      <form className="mp-form-grid" onSubmit={submitBuyerProfile}>
        <Field label={mt('fullName')} value={buyerForm.full_name} required onChange={(value) => setBuyerForm({ ...buyerForm, full_name: value })} />
        <Field label={mt('businessName')} value={buyerForm.business_name} onChange={(value) => setBuyerForm({ ...buyerForm, business_name: value })} />
        <label className="mp-field"><span>{mt('buyerType')} <b>*</b></span><select value={buyerForm.buyer_type} onChange={(event) => setBuyerForm({ ...buyerForm, buyer_type: event.target.value })}>{localizedBuyerTypes.map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}</select></label>
        <Field label={mt('phone')} type="tel" value={buyerForm.phone} required onChange={(value) => setBuyerForm({ ...buyerForm, phone: value })} />
        <Field label={mt('whatsapp')} type="tel" value={buyerForm.whatsapp} required onChange={(value) => setBuyerForm({ ...buyerForm, whatsapp: value })} />
        <Field label={mt('email')} type="email" value={buyerForm.email} onChange={(value) => setBuyerForm({ ...buyerForm, email: value })} />
        <Field label={mt('deliveryLocation')} value={buyerForm.delivery_location} required onChange={(value) => setBuyerForm({ ...buyerForm, delivery_location: value })} />
        <Field label={mt('address')} value={buyerForm.address} onChange={(value) => setBuyerForm({ ...buyerForm, address: value })} />
        <div className="mp-field mp-field--wide">
          <span>{mt('cropPreferences')} <b>*</b></span>
          <input value={buyerForm.crop_preferences.join(', ')} placeholder={mt('searchPlaceholder')} onChange={(event) => setBuyerForm({ ...buyerForm, crop_preferences: event.target.value.split(',').map((item) => item.trim()).filter(Boolean) })} required />
          <small>{mt('preferencesHint')}</small>
        </div>
        <label className="mp-field mp-field--wide"><span>{mt('additionalInfo')}</span><textarea rows="3" maxLength="1500" value={buyerForm.additional_info} onChange={(event) => setBuyerForm({ ...buyerForm, additional_info: event.target.value })} /></label>
        <div className="mp-form-actions"><GradientButton type="submit" loading={saving}>{buyerProfile ? mt('saveChanges') : mt('createProfile')}</GradientButton></div>
      </form>
    </GlassCard>
  )

  const renderRequirementForm = () => (
    <GlassCard className="mp-form-card">
      <div className="mp-section-heading">
        <div><span className="mp-eyebrow">{mt('connectNearby')}</span><h2>{editingRequirement ? mt('editRequirement') : mt('postRequirement')}</h2><p>{mt('openOnly')}</p></div>
      </div>
      {!buyerProfile ? <EmptyState title={mt('createProfileFirst')} text={mt('profileSuppliesContact')} action={() => navigateTab('profile')} actionText={mt('setupBuyerProfile')} /> : (
        <form className="mp-form-grid" onSubmit={submitRequirement}>
          <Field label={mt('cropOrVegetable')} value={requirementForm.crop} required onChange={(value) => setRequirementForm({ ...requirementForm, crop: value })} />
          <SelectField label={mt('category')} value={requirementForm.category} options={localizedCategories} onChange={(value) => setRequirementForm({ ...requirementForm, category: value })} />
          <Field label={mt('requiredQuantity')} type="number" min="0.01" step="any" value={requirementForm.quantity} required onChange={(value) => setRequirementForm({ ...requirementForm, quantity: value })} />
          <SelectField label={mt('unit')} value={requirementForm.unit} options={localizedUnits} onChange={(value) => setRequirementForm({ ...requirementForm, unit: value })} />
          <Field label={mt('expectedPriceUnit')} type="number" min="0.01" step="any" value={requirementForm.expected_price_per_unit} required onChange={(value) => setRequirementForm({ ...requirementForm, expected_price_per_unit: value })} />
          <Field label={mt('deliveryLocationField')} value={requirementForm.delivery_location} required onChange={(value) => setRequirementForm({ ...requirementForm, delivery_location: value })} />
          <Field label={mt('requiredDeliveryDate')} type="date" min={tomorrow()} value={requirementForm.delivery_date} required onChange={(value) => setRequirementForm({ ...requirementForm, delivery_date: value })} />
          <label className="mp-field"><span>{mt('qualityPreferencesField')}</span><input value={requirementForm.quality_preferences} maxLength="500" onChange={(event) => setRequirementForm({ ...requirementForm, quality_preferences: event.target.value })} placeholder={mt('qualityPlaceholder')} /></label>
          <label className="mp-field mp-field--wide"><span>{mt('additionalDescription')}</span><textarea rows="3" maxLength="2000" value={requirementForm.description} onChange={(event) => setRequirementForm({ ...requirementForm, description: event.target.value })} /></label>
          <div className="mp-budget mp-field--wide"><span>{mt('estimatedBudgetLabel')}</span><strong>{formatRupees(estimatedBudget)}</strong><small>{mt('budgetCalculated')}</small></div>
          <div className="mp-form-actions"><GradientButton type="submit" loading={saving}>{editingRequirement ? mt('saveRequirement') : mt('postRequirement')}</GradientButton><button className="mp-secondary-btn" type="button" onClick={() => { setEditingRequirement(''); setRequirementForm(emptyRequirement()); navigateTab('myRequirements') }}>{mt('cancel')}</button></div>
        </form>
      )}
    </GlassCard>
  )

  const renderProduceForm = () => (
    <GlassCard className="mp-form-card">
      <div className="mp-section-heading"><div><span className="mp-eyebrow">{mt('farmerListing')}</span><h2>{editingProduce ? `${mt('edit')} ${translatePlantVillageCrop(produceForm.crop, t)}` : mt('listAvailable')}</h2><p>{mt('draftPrivate')}</p></div></div>
      {!farmerProfile ? <EmptyState title={mt('farmerProfileRequired')} text={mt('completeFarmerProfile')} action={() => window.location.assign('/create-profile')} actionText={mt('completeFarmerProfile')} /> : (
        <form className="mp-form-grid" onSubmit={submitProduce}>
          <Field label={mt('cropOrVegetable')} value={produceForm.crop} required disabled={editingProfileCrop} onChange={(value) => setProduceForm({ ...produceForm, crop: value })} />
          <SelectField label={mt('category')} value={produceForm.category} options={localizedCategories} onChange={(value) => setProduceForm({ ...produceForm, category: value })} />
          <Field label={`${mt('availableQuantityLabel')} (${displayUnit(produceForm.unit)})`} type="number" min="0" step="any" value={produceForm.quantity} onChange={(value) => setProduceForm({ ...produceForm, quantity: value })} />
          {editingProfileCrop ? <Field label={mt('unit')} value="kg" disabled onChange={() => {}} /> : <SelectField label={mt('unit')} value={produceForm.unit} options={localizedUnits} onChange={(value) => setProduceForm({ ...produceForm, unit: value })} />}
          <Field label={mt('pricePerUnit', { unit: displayUnit(produceForm.unit) })} type="number" min="0" step="any" value={produceForm.price_per_unit} onChange={(value) => setProduceForm({ ...produceForm, price_per_unit: value })} />
          <Field label={mt('minimumOrderOptional', { unit: displayUnit(produceForm.unit) })} type="number" min="0.01" step="any" value={produceForm.min_order_quantity} onChange={(value) => setProduceForm({ ...produceForm, min_order_quantity: value })} />
          <Field label={mt('availableFrom')} type="date" min={tomorrow()} value={produceForm.available_from} onChange={(value) => setProduceForm({ ...produceForm, available_from: value })} />
          <Field label={mt('location')} value={produceForm.location} required onChange={(value) => setProduceForm({ ...produceForm, location: value })} />
          <Field label={`${mt('productImageUrl')} (${t('common.optional')})`} type="url" value={produceForm.image_url} onChange={(value) => setProduceForm({ ...produceForm, image_url: value })} />
          <label className="mp-field mp-field--wide"><span>{mt('description')}</span><textarea rows="3" maxLength="1200" value={produceForm.description} onChange={(event) => setProduceForm({ ...produceForm, description: event.target.value })} /></label>
          <label className="mp-publish-toggle"><input type="checkbox" checked={Boolean(produceForm.publish)} onChange={(event) => setProduceForm({ ...produceForm, publish: event.target.checked })} /><span><strong>{mt('publish')}</strong><small>{mt('publishHint')}</small></span></label>
          {produceFormError && <p role="alert" className="mp-chat-error mp-field--wide">{produceFormError}</p>}
          <div className="mp-form-actions"><GradientButton type="submit" loading={saving}>{produceForm.publish ? mt('publish') : mt('draft')}</GradientButton><button className="mp-secondary-btn" type="button" onClick={() => { setEditingProduce(''); setEditingProfileCrop(false); setProduceForm(emptyProduce()); setProduceFormError(''); navigateTab('myProduce') }}>{mt('cancel')}</button></div>
        </form>
      )}
    </GlassCard>
  )

  const renderProduce = () => (
    <>
      <section className="mp-hero">
        <div className="mp-hero-copy"><span className="mp-eyebrow">{t('brand.projectName')} Marketplace</span><h1>Fresh from Farms,<br /><em>Direct to You</em></h1><p>Discover real produce listings and connect with the farmers growing your next harvest.</p></div>
        <div className="mp-hero-mark" aria-hidden="true">🌱</div>
        <form className="mp-search" onSubmit={searchProducts}>
          <span aria-hidden="true">⌕</span><input aria-label="Search crops and vegetables" placeholder="Search crops and vegetables..." value={searchText} onChange={(event) => setSearchText(event.target.value)} /><button type="submit">Search produce</button>
        </form>
      </section>
      <div className="mp-filter-row">
        <SelectField label={mt('category')} value={filters.category} options={[{ value: '', label: t('common.all') }, ...localizedCategories]} onChange={(value) => setFilters({ ...filters, category: value })} />
        <Field label={mt('location')} value={filters.location} placeholder={mt('locationPlaceholder')} onChange={(value) => setFilters({ ...filters, location: value })} />
        <button className="mp-text-btn" onClick={() => { setFilters({ crop: '', location: '', category: '' }); setSearchText('') }}>{mt('clearFilters')}</button>
      </div>
      {isFarmer && <div className="mp-inline-action"><span>Growing something for the market?</span><GradientButton size="sm" onClick={startNewProduce}>List your produce</GradientButton></div>}
      <div className="mp-section-heading"><div><span className="mp-eyebrow">The latest harvest</span><h2>Available produce</h2></div><span className="mp-count">{produce.length} listings</span></div>
      {loading ? <Loading /> : produce.length ? <div className="mp-product-grid">{produce.map((item) => {
        const cropName = translatePlantVillageCrop(item.crop, t)
        return <article className="mp-product-card" key={item.id}>
        <div className="mp-product-image"><img src={getCropImage(item.crop) || item.image_url || CROP_IMAGE_FALLBACK} style={{ objectPosition: getCropImagePosition(item.crop) }} alt={`${cropName} produce`} loading="lazy" onError={(event) => { event.currentTarget.onerror = null; event.currentTarget.src = CROP_IMAGE_FALLBACK }} /><span>{item.category || 'Fresh produce'}</span></div>
        <div className="mp-product-body"><div className="mp-product-heading"><h3>{cropName}</h3><strong>{formatRupees(item.price_per_unit)}<small> / {displayUnit(item.unit)}</small></strong></div><p className="mp-muted">By {localizeDisplayName(item.farmer_name || mt('localFarmer'), language)} · {localizeLocation(item.location, language)}</p><p className="mp-quantity">{displayQuantity(item.quantity, item.unit)} {mt('available')}</p>{item.min_order_quantity && <p className="mp-muted">{mt('minimumOrder')}: {displayQuantity(item.min_order_quantity, item.unit)}</p>}{item.description && <p className="mp-description">{item.description}</p>}
          <div className="mp-card-actions"><button className="mp-secondary-btn" onClick={() => setSelectedProduce(selectedProduce?.id === item.id ? null : item)}>{selectedProduce?.id === item.id ? 'Hide details' : 'View Details'}</button>{isBuyer && <button className="mp-primary-btn" onClick={() => openListingOrder(item)}>Place Order</button>}</div>
          {selectedProduce?.id === item.id && <div className="mp-detail-note">{mt('farmer')}: {localizeDisplayName(item.farmer_name || mt('localFarmer'), language)} · {mt('location')}: {localizeLocation(item.location, language)} · {displayQuantity(item.quantity, item.unit)} {mt('currentlyAvailable')}.</div>}
        </div>
      </article>})}</div> : <EmptyState title="No produce listings yet" text="When farmers publish available crops, they will appear here. Try adjusting your filters or check back soon." action={isFarmer ? startNewProduce : null} actionText="List available produce" />}
    </>
  )

  const renderRequirements = () => {
    const buyerView = tab === 'myRequirements' || (!isFarmer && isBuyer)
    return <>
      <section className="mp-page-heading"><span className="mp-eyebrow">{buyerView ? 'Your purchasing activity' : 'Opportunities for local growers'}</span><h1>{buyerView ? 'My Requirements' : 'Available Crop Opportunities'}</h1><p>{buyerView ? 'Manage your active requests and compare farmer offers.' : 'Browse open crop requests and send a competitive offer.'}</p></section>
      {isFarmer && <form className="mp-filter-row mp-requirement-filter" onSubmit={(event) => { event.preventDefault(); loadTab() }}><Field label="Crop" value={requirementFilters.crop} onChange={(value) => setRequirementFilters({ ...requirementFilters, crop: value })} /><Field label="Delivery location" value={requirementFilters.location} onChange={(value) => setRequirementFilters({ ...requirementFilters, location: value })} /><Field label="Min quantity" type="number" min="0" value={requirementFilters.min_quantity} onChange={(value) => setRequirementFilters({ ...requirementFilters, min_quantity: value })} /><Field label="Max quantity" type="number" min="0" value={requirementFilters.max_quantity} onChange={(value) => setRequirementFilters({ ...requirementFilters, max_quantity: value })} /><Field label="Min price (₹/unit)" type="number" min="0" value={requirementFilters.min_price} onChange={(value) => setRequirementFilters({ ...requirementFilters, min_price: value })} /><Field label="Max price (₹/unit)" type="number" min="0" value={requirementFilters.max_price} onChange={(value) => setRequirementFilters({ ...requirementFilters, max_price: value })} /><GradientButton type="submit">Filter requirements</GradientButton></form>}
      {buyerView && <div className="mp-toolbar"><GradientButton onClick={() => { setRequirementForm(emptyRequirement()); setEditingRequirement(''); navigateTab('postRequirement') }}>＋ Post a requirement</GradientButton></div>}
      {loading ? <Loading /> : requirements.length ? <div className="mp-requirement-list">{requirements.map((item) => <GlassCard className="mp-requirement-card" key={item.id}>
        <div className="mp-requirement-top"><div><span className={`mp-status mp-status--${item.status}`}>{item.status?.replace('_', ' ')}</span><h3>{translatePlantVillageCrop(item.crop, t)}</h3><p>{localizeDisplayName(item.buyer_name, language)}{item.business_name ? ` · ${item.business_name}` : ''}{(buyerView || isFarmer) && <span className="mp-muted"> · Contact: {item.buyer_phone || 'Contact number not provided'}</span>}</p></div><div className="mp-budget-value">{formatRupees(item.estimated_budget)}<small>estimated budget</small></div></div>
        <div className="mp-facts"><Fact label={mt('quantity')} value={displayQuantity(item.quantity, item.unit)} /><Fact label={mt('expectedPrice')} value={`${formatRupees(item.expected_price_per_unit)} / ${displayUnit(item.unit)}`} /><Fact label={mt('delivery')} value={localizeLocation(item.delivery_location, language)} /><Fact label={mt('requiredBy')} value={item.delivery_date} /></div>
        {(item.quality_preferences || item.description) && <p className="mp-description">{item.quality_preferences && <><b>Quality:</b> {item.quality_preferences}　</>}{item.description}</p>}
        <div className="mp-card-actions">{buyerView && <><button className="mp-secondary-btn" onClick={() => showOffers(item)}>View offers</button>{['open', 'offer_submitted'].includes(item.status) && <button className="mp-secondary-btn" onClick={() => openRequirementEditor(item)}>Edit</button>}{['open', 'offer_submitted'].includes(item.status) && <button className="mp-danger-btn" onClick={() => cancelRequirement(item)}>Cancel</button>}</>}{isFarmer && <button className="mp-primary-btn" onClick={() => setOfferingRequirement(offeringRequirement === item.id ? '' : item.id)}>{offeringRequirement === item.id ? 'Close offer form' : 'Submit an offer'}</button>}</div>
        {offeringRequirement === item.id && <form className="mp-offer-form" onSubmit={submitOffer}><h4>Send your offer for {translatePlantVillageCrop(item.crop, t)}</h4><div className="mp-form-grid"><Field label={`${mt('quantity')} (${displayUnit(item.unit)})`} type="number" min="0.01" max={item.quantity} step="any" value={offerForm.quantity} required onChange={(value) => setOfferForm({ ...offerForm, quantity: value })} /><Field label={`${mt('pricePerUnit', { unit: displayUnit(item.unit) })} (₹)`} type="number" min="0.01" step="any" value={offerForm.price_per_unit} required onChange={(value) => setOfferForm({ ...offerForm, price_per_unit: value })} /><Field label={mt('requiredDeliveryDate')} type="date" min={tomorrow()} value={offerForm.delivery_date} required onChange={(value) => setOfferForm({ ...offerForm, delivery_date: value })} /><label className="mp-field mp-field--wide"><span>{mt('optionalMessage')}</span><textarea rows="2" maxLength="1500" value={offerForm.message} onChange={(event) => setOfferForm({ ...offerForm, message: event.target.value })} /></label></div><p className="mp-budget">{mt('expectedPrice')} <strong>{formatRupees(Number(offerForm.quantity || 0) * Number(offerForm.price_per_unit || 0))}</strong></p><GradientButton type="submit" loading={saving}>Send offer</GradientButton></form>}
        {requirementOffers[item.id] && <div className="mp-offers-list"><h4>Offers received ({requirementOffers[item.id].length})</h4>{requirementOffers[item.id].length ? requirementOffers[item.id].map((offer) => <div className="mp-offer-row" key={offer.id}><div><strong>{offer.farmer_name}</strong><p>{displayQuantity(offer.quantity, offer.unit)} · {formatRupees(offer.price_per_unit)} / {displayUnit(offer.unit)} · {offer.delivery_date}</p><small>Total {formatRupees(offer.total_amount)}{offer.farmer_location ? ` · ${localizeLocation(offer.farmer_location, language)}` : ''}</small>{offer.message && <p>{offer.message}</p>}</div><span className={`mp-status mp-status--${offer.status}`}>{offer.status}</span>{offer.status === 'submitted' && item.status !== 'accepted' && <div className="mp-offer-actions"><button className="mp-primary-btn" onClick={() => decideOffer(item.id, offer.id, 'accept')}>Accept</button><button className="mp-danger-btn" onClick={() => decideOffer(item.id, offer.id, 'reject')}>Reject</button></div>}</div>) : <p className="mp-muted">No offers have arrived yet.</p>}</div>}
      </GlassCard>)}</div> : <EmptyState title={buyerView ? 'No requirements yet' : 'No open requirements nearby'} text={buyerView ? 'Post your first request and farmers can send you offers.' : 'Check back soon for new crop and vegetable requests from buyers.'} action={buyerView ? () => navigateTab('postRequirement') : null} actionText="Post Your Requirement" />}
    </>
  }

  const renderMyRequirements = () => {
    if (tab !== 'myRequirements') return null
    return renderRequirements()
  }

  const renderOrders = () => {
    const visibleOrders = orders
    return (
    <>
      <section className="mp-page-heading"><span className="mp-eyebrow">{mt('ordersEyebrow')}</span><h1>{mt('ordersTitle')}</h1><p>{mt('ordersPrivacy')}</p></section>
      {loading ? <Loading /> : visibleOrders.length ? <div className="mp-requirement-list">{visibleOrders.map((order) => {
        const detail = orderDetails[order.id]
        const otherParty = detail?.buyer_id === user?.id ? detail?.contacts?.farmer : detail?.contacts?.buyer
        const mobileNumber = otherParty?.phone || otherParty?.whatsapp || ''
        const contactNumber = whatsappNumber(mobileNumber)
        const cropName = translatePlantVillageCrop(order.crop, t)
        return         <GlassCard className={`mp-order-card${highlightedOrder === order.id ? ' mp-order-card--highlighted' : ''}`} key={order.id} id={`order-${order.id}`}>
          <div className="mp-requirement-top"><div><span className={`mp-status mp-status--${order.status}`}>{orderStatusLabel(order.status)}</span><h3>{cropName}</h3><p>{mt('marketplaceOrder')} #{order.id.slice(-8).toUpperCase()}{order.direct_listing_order ? ` · ${localizeDisplayName(isFarmer ? order.buyer_name || mt('buyer') : order.farmer_name || mt('farmer'), language)}` : ''}</p></div><div className="mp-budget-value">{formatRupees(order.total_amount)}<small>{mt('orderTotal')}</small></div></div>
          <div className="mp-facts"><Fact label={mt('quantity')} value={displayQuantity(order.quantity, order.unit)} /><Fact label={mt('price')} value={`${formatRupees(order.price_per_unit)} / ${displayUnit(order.unit)}`} /><Fact label={mt('deliveryLocationField')} value={localizeLocation(order.delivery_location, language)} /><Fact label={mt('deliveryAddress')} value={order.delivery_address || mt('locationNotProvided')} /><Fact label={mt('deliveryDate')} value={order.delivery_date ? formatDate(order.delivery_date, { dateStyle: 'medium' }) : mt('locationNotProvided')} /><Fact label={mt('orderDate')} value={order.created_at ? formatDate(order.created_at, { dateStyle: 'medium' }) : mt('locationNotProvided')} /></div>
          {order.message && <p className="mp-description">{mt('message')}: {order.message}</p>}
          {detail?.contacts && <div className="mp-contact-row"><strong>{mt('orderPartner')}: {localizeDisplayName(otherParty?.name || mt('participant'), language)}</strong><span>{mt('mobile')}: {mobileNumber || mt('mobileUnavailable')}</span>{contactNumber && <a href={`tel:+${contactNumber}`}>{mt('call')}</a>}{contactNumber && <a href={`https://wa.me/${contactNumber}`} target="_blank" rel="noreferrer">{mt('whatsapp')}</a>}{otherParty?.email && <a href={`mailto:${otherParty.email}`}>{mt('email')}</a>}</div>}
          <div className="mp-card-actions">{isBuyer && order.direct_listing_order && <button className="mp-secondary-btn" onClick={() => viewFarmerProfile(order.farmer_id)}>{mt('viewFarmerProfile')}</button>}<button className="mp-secondary-btn" onClick={() => openOrderChat(order.id)}>{mt('openChat')}</button>{isFarmer && order.direct_listing_order && order.status === 'pending' && <><button className="mp-primary-btn" onClick={() => decideListingOrder(order, 'accept')}>{mt('accept')}</button><button className="mp-danger-btn" onClick={() => decideListingOrder(order, 'reject')}>{mt('reject')}</button></>}{isBuyer && order.direct_listing_order && order.status === 'pending' && <button className="mp-danger-btn" onClick={() => cancelListingOrder(order)}>{mt('cancelOrder')}</button>}{order.status === 'accepted' && <button className="mp-primary-btn" onClick={() => marketplaceApi.updateOrderStatus(order.id, 'in_progress').then(loadTab).catch((error) => notify('error', errorMessage(error)))}>{mt('markInProgress')}</button>}{order.status === 'in_progress' && <button className="mp-primary-btn" onClick={() => marketplaceApi.updateOrderStatus(order.id, 'completed').then(loadTab).catch((error) => notify('error', errorMessage(error)))}>{mt('markCompleted')}</button>}</div>
        </GlassCard>
      })}</div> : <EmptyState title={mt('noOrders')} text={tab === 'incomingOrders' ? mt('incomingOrdersEmpty') : mt('outgoingOrdersEmpty')} />}
    </>
    )
  }

  const renderDashboard = () => (
    <>
      <section className="mp-page-heading"><span className="mp-eyebrow">Your marketplace at a glance</span><h1>{isBuyer ? 'Buyer Dashboard' : 'Farmer Marketplace Dashboard'}</h1><p>Welcome, {user?.full_name || user?.name || (isBuyer ? 'buyer' : 'farmer')}.</p></section>
      {!overview ? <Loading /> : <div className="mp-dashboard-columns">
        {overview.is_buyer && <section><div className="mp-section-heading"><div><span className="mp-eyebrow">Buyer overview</span><h2>Buying activity</h2></div></div><div className="mp-stat-grid">{[['Total requirements', overview.buyer.requirements], ['Active requirements', overview.buyer.active_requirements], ['Offers received', overview.buyer.offers_received], ['Accepted offers', overview.buyer.accepted_offers], ['Active orders', overview.buyer.active_orders], ['Completed orders', overview.buyer.completed_orders]].map(([label, count]) => <div className="mp-stat" key={label}><strong>{count}</strong><span>{label}</span></div>)}</div><div className="mp-toolbar"><GradientButton onClick={() => navigateTab('myRequirements')}>My Requirements</GradientButton><button className="mp-secondary-btn" onClick={() => navigateTab('orders')}>My Orders</button><button className="mp-secondary-btn" onClick={() => navigateTab('profile')}>Edit Profile</button></div></section>}
        {overview.is_farmer && <section><div className="mp-section-heading"><div><span className="mp-eyebrow">Farmer overview</span><h2>Selling activity</h2></div></div><div className="mp-stat-grid">{[['Available requirements', overview.farmer.available_requirements], ['Accepted offers', overview.farmer.accepted_offers], ['Active orders', overview.farmer.active_orders], ['Completed orders', overview.farmer.completed_orders]].map(([label, count]) => <div className="mp-stat" key={label}><strong>{count}</strong><span>{label}</span></div>)}</div><div className="mp-toolbar"><button className="mp-secondary-btn" onClick={() => navigateTab('orders')}>My Orders</button><button className="mp-secondary-btn" onClick={() => navigateTab('myProduce')}>My Listings</button></div></section>}
        {!overview.is_buyer && !overview.is_farmer && <EmptyState title="Account role unavailable" text="Sign out and sign in again so your account role can be verified." />}
      </div>}
    </>
  )

  const renderMyProduce = () => (
    <>
      <section className="mp-page-heading"><span className="mp-eyebrow">{mt('myListingsEyebrow')}</span><h1>{mt('myListingsTitle')}</h1><p>{mt('myListingsHint')}</p></section>
      {loading ? <Loading /> : produce.length ? <div className="mp-product-grid">{produce.map((item) => {
        const draft = item.status === 'draft'
        const paused = item.status === 'paused_profile'
        const editable = ['available', 'draft', 'sold'].includes(item.status)
        const editing = editingProduce === item.id
        const cropName = translatePlantVillageCrop(item.crop, t)
        return <article className="mp-product-card mp-my-listing-card" key={item.id}>
          <div className="mp-product-image"><img src={getCropImage(item.crop) || item.image_url || CROP_IMAGE_FALLBACK} style={{ objectPosition: getCropImagePosition(item.crop) }} alt={`${cropName} produce`} loading="lazy" onError={(event) => { event.currentTarget.onerror = null; event.currentTarget.src = CROP_IMAGE_FALLBACK }} /><span className={`mp-listing-status mp-listing-status--${item.status}`}>{draft ? mt('statusDraft') : paused ? mt('statusPaused') : item.status === 'available' ? mt('statusActive') : item.status === 'sold' ? mt('statusSold') : item.status}</span></div>
          <div className="mp-product-body"><h3>{cropName}</h3>
            {editing ? (
              <form className="mp-listing-editor" onSubmit={(event) => { event.preventDefault(); saveProduceCard(item) }}>
                <SelectField label={mt('category')} value={produceForm.category} options={localizedCategories} onChange={(value) => setProduceForm((current) => ({ ...current, category: value }))} />
                <Field label={`${mt('pricePerUnit', { unit: displayUnit(produceForm.unit) })} (₹)`} type="number" min="0" step="any" value={produceForm.price_per_unit} onChange={(value) => setProduceForm((current) => ({ ...current, price_per_unit: value }))} />
                <Field label={`${mt('availableQuantity')} (${displayUnit(produceForm.unit)})`} type="number" min="0" step="any" value={produceForm.quantity} onChange={(value) => setProduceForm((current) => ({ ...current, quantity: value }))} />
                <Field label={mt('minimumOrderOptional', { unit: displayUnit(produceForm.unit) })} type="number" min="0.01" step="any" value={produceForm.min_order_quantity} onChange={(value) => setProduceForm((current) => ({ ...current, min_order_quantity: value }))} />
                <Field label={mt('availabilityDateOptional')} type="date" value={produceForm.available_from} onChange={(value) => setProduceForm((current) => ({ ...current, available_from: value }))} />
                <label className="mp-field mp-listing-editor__description"><span>{mt('descriptionOptional')}</span><textarea rows="3" maxLength="1200" value={produceForm.description} onChange={(event) => setProduceForm((current) => ({ ...current, description: event.target.value }))} /></label>
                <label className="mp-publish-toggle mp-listing-editor__publish"><input type="checkbox" checked={Boolean(produceForm.publish)} onChange={(event) => setProduceForm((current) => ({ ...current, publish: event.target.checked }))} /><span><strong>{mt('publishToMarketplace')}</strong><small>{mt('positivePriceQuantityHint')}</small></span></label>
                {produceFormError && <p role="alert" className="mp-chat-error mp-field--wide">{produceFormError}</p>}
                <div className="mp-card-actions mp-listing-editor__actions">
                  <button className="mp-primary-btn" type="submit" disabled={saving}>{saving ? mt('saving') : mt('saveListing')}</button>
                  <button className="mp-secondary-btn" type="button" disabled={saving} onClick={cancelProduceEdit}>{mt('cancelListingEdit')}</button>
                  <button className="mp-danger-btn" type="button" disabled={saving} onClick={() => removeProduce(item)}>{mt('deleteListing')}</button>
                </div>
              </form>
            ) : <>
            {draft && <p className="mp-listing-draft-note">{mt('addPriceQuantityHint')}</p>}
            {paused && <p className="mp-listing-draft-note">{mt('removedProfileListing')}</p>}
            <div className="mp-listing-facts"><span><small>{mt('pricePerUnit', { unit: displayUnit(item.unit) })}</small><strong>{Number(item.price_per_unit) > 0 ? `${formatRupees(item.price_per_unit)} / ${displayUnit(item.unit)}` : mt('notSetLabel')}</strong></span><span><small>{mt('availableQuantityLabel')}</small><strong>{Number(item.quantity) > 0 ? displayQuantity(item.quantity, item.unit) : mt('notSetLabel')}</strong></span></div>
            {item.min_order_quantity && <p className="mp-muted">{mt('minimumOrder')}: {displayQuantity(item.min_order_quantity, item.unit)}</p>}
            {item.available_from && <p className="mp-muted">{mt('availableFrom')} {new Date(item.available_from).toLocaleDateString()}</p>}
            {item.location && <p>{localizeLocation(item.location, language)}</p>}
            <div className="mp-card-actions">{editable && <button className="mp-secondary-btn" onClick={() => editProduce(item)}>{mt('edit')}</button>}<button className="mp-danger-btn" onClick={() => removeProduce(item)}>{mt('deleteListing')}</button></div>
            </>}
          </div>
        </article>
      })}</div> : <EmptyState title={mt('noMyListings')} text={mt('noMyListingsHint')} action={() => navigate('/profile')} actionText={mt('updateFarmerProfile')} />}
    </>
  )

  const viewFarmerProfile = (farmerId) => {
    setSearchParams({ tab: 'farmerProfile', farmerId })
  }

  const renderFarmers = () => (
    <>
      <section className="mp-page-heading"><span className="mp-eyebrow">Discover local growers</span><h1>Farmer Directory</h1><p>Browse farmers who chose to make their profile visible. Private contact details are not shown here.</p></section>
      <form className="mp-filter-row mp-farmer-filter" onSubmit={(event) => { event.preventDefault(); loadTab() }}>
        <Field label="Farmer name" value={farmerFilters.name} onChange={(value) => setFarmerFilters({ ...farmerFilters, name: value })} />
        <Field label="Location" value={farmerFilters.location} onChange={(value) => setFarmerFilters({ ...farmerFilters, location: value })} />
        <Field label="Available crop" value={farmerFilters.crop} onChange={(value) => setFarmerFilters({ ...farmerFilters, crop: value })} />
        <GradientButton type="submit">Search farmers</GradientButton>
      </form>
      {loading ? <Loading /> : farmers.length ? <div className="mp-farmer-grid">{farmers.map((farmer) => <GlassCard className="mp-farmer-card" key={farmer.id}>
        <div className="mp-farmer-avatar">{farmer.profile_photo_url ? <img src={farmer.profile_photo_url} alt="" /> : <span aria-hidden="true">👨‍🌾</span>}</div>
        <div className="mp-farmer-card-content"><h2>{localizeDisplayName(farmer.full_name, language)}</h2><p>{localizeLocation(farmer.location, language) || mt('locationNotProvided')}</p><div className="mp-crop-chips">{farmer.available_crops.map((crop) => <span key={crop}>{translatePlantVillageCrop(crop, t)}</span>)}{!farmer.available_crops.length && <span>No current produce</span>}</div><small>{farmer.available_listings} available listings</small></div>
        <button className="mp-secondary-btn" onClick={() => viewFarmerProfile(farmer.id)}>View Profile</button>
      </GlassCard>)}</div> : <EmptyState title="No discoverable farmers found" text="Try changing your search, or check back when farmers have opted in to the public directory." />}
    </>
  )

  const renderPublicFarmerProfile = () => (
    <>
      {!publicFarmer ? <Loading /> : <>
        <section className="mp-public-farmer">
          <div className="mp-farmer-avatar mp-farmer-avatar--large">{publicFarmer.profile_photo_url ? <img src={publicFarmer.profile_photo_url} alt={`${localizeDisplayName(publicFarmer.full_name, language)} profile`} /> : <span aria-hidden="true">👨‍🌾</span>}</div>
          <div><span className="mp-eyebrow">Public farmer profile</span><h1>{localizeDisplayName(publicFarmer.full_name, language)}</h1><p>{localizeLocation(publicFarmer.location_label, language) || mt('locationNotProvided')}</p><div className="mp-crop-chips">{(publicFarmer.farming?.crops || [publicFarmer.farming?.crop].filter(Boolean)).map((crop) => <span key={crop}>{translatePlantVillageCrop(crop, t)}</span>)}</div><div className="mp-public-profile-facts"><Fact label="Main crop" value={translatePlantVillageCrop(publicFarmer.farming?.crop, t)} />          <Fact label={t('myProfile.variety')} value={localizeVariety(publicFarmer.farming?.variety, language)} /><Fact label="Crop stage" value={publicFarmer.farming?.stage} /><Fact label="Land area" value={publicFarmer.farming?.land_area ? `${publicFarmer.farming.land_area} ${publicFarmer.farming.land_unit}` : ''} /><Fact label="Soil" value={publicFarmer.farming?.soil_type} /><Fact label="Irrigation" value={publicFarmer.farming?.irrigation} /></div></div>
          <div className="mp-card-actions">
            <button className="mp-secondary-btn" onClick={() => navigateTab('farmers')}>Back to directory</button>
            {isBuyer && <button className="mp-primary-btn" onClick={() => {
              if (!buyerProfile) {
                notify('error', 'Complete your buyer profile before sending an order request.')
                navigateTab('profile')
                return
              }
              openFarmerOrderRequest()
            }}>Send Order Request</button>}
          </div>
        </section>
        <div className="mp-section-heading"><div><span className="mp-eyebrow">Available from this farm</span><h2>Current produce listings</h2></div><span className="mp-count">{publicFarmer.listings.length} listings</span></div>
        {publicFarmer.listings.length ? <div className="mp-product-grid">{publicFarmer.listings.map((item) => <article className="mp-product-card" key={item.id}>
          <div className="mp-product-image"><img src={getCropImage(item.crop) || item.image_url || CROP_IMAGE_FALLBACK} style={{ objectPosition: getCropImagePosition(item.crop) }} alt={`${item.crop} produce`} loading="lazy" onError={(event) => { event.currentTarget.onerror = null; event.currentTarget.src = CROP_IMAGE_FALLBACK }} /><span>{item.category || 'Fresh produce'}</span></div>
          <div className="mp-product-body"><div className="mp-product-heading"><h3>{translatePlantVillageCrop(item.crop, t)}</h3><strong>{formatRupees(item.price_per_unit)}<small> / {displayUnit(item.unit)}</small></strong></div><p className="mp-muted">{localizeLocation(item.location, language)}</p><p className="mp-quantity">{displayQuantity(item.quantity, item.unit)} {mt('availableQuantityLabel')}</p>{item.description && <p className="mp-description">{item.description}</p>}<div className="mp-card-actions"><button className="mp-primary-btn" onClick={() => openListingOrder(item)}>Place Order</button></div></div>
        </article>)}</div> : <EmptyState title="No available produce" text="This farmer has no active listings right now." />}
      </>}
    </>
  )

  const renderNotifications = () => (
    <>
      <section className="mp-page-heading"><span className="mp-eyebrow">Order updates</span><h1>Notifications</h1><p>Updates are stored in your account. No SMS, email or push notification is sent.</p></section>
      {loading ? <Loading /> : notifications.length ? <div className="mp-requirement-list">{notifications.map((item) => <GlassCard className={`mp-notification-card${item.is_read ? '' : ' mp-notification-card--unread'}`} key={item.id}>
        <div><span className={`mp-status mp-status--${item.is_read ? 'completed' : 'pending'}`}>{item.is_read ? 'Read' : 'New'}</span><p>{item.message}</p><small>{item.created_at ? new Date(item.created_at).toLocaleString() : ''}</small></div>
        <button className="mp-primary-btn" onClick={async () => {
          try {
            if (!item.is_read) await marketplaceApi.markNotificationRead(item.id)
            setNotifications((current) => current.map((notification) => notification.id === item.id ? { ...notification, is_read: true } : notification))
            setHighlightedOrder(item.order_id)
            navigateTab('orders')
          } catch (error) { notify('error', errorMessage(error)) }
        }}>Open order</button>
      </GlassCard>)}</div> : <EmptyState title="You're all caught up" text="When a farmer accepts or rejects one of your orders, the update will appear here." />}
    </>
  )

  const sendChatMessage = async (event) => {
    event.preventDefault()
    if (!activeChatOrder || !chatText.trim() || chatSendLock.current) return
    chatSendLock.current = true
    setChatSending(true)
    setChatLoadError('')
    try {
      const sent = await marketplaceApi.sendOrderMessage(activeChatOrder, chatText, {
        client_message_id: crypto.randomUUID(),
        ...(chatReply?.id ? { reply_to_id: chatReply.id } : {})
      })
      setChatMessages((current) => (
        current.some((message) => message.id === sent.id) ? current : [...current, sent]
      ).sort((left, right) => new Date(left.created_at) - new Date(right.created_at)))
      setChatText('')
      setChatReply(null)
      setEmojiPickerOpen(false)
      const updatedConversations = await marketplaceApi.getConversations()
      setChatConversations(updatedConversations)
      setOrders(updatedConversations)
    } catch (error) {
      setChatLoadError(errorMessage(error))
    } finally {
      chatSendLock.current = false
      setChatSending(false)
    }
  }

  const deleteChatMessage = async (message, scope) => {
    const prompt = scope === 'everyone'
      ? 'Delete this message for both participants?'
      : 'Hide this message from your chat? The other participant will still see it.'
    if (!window.confirm(prompt)) return
    setChatActionMenu('')
    try {
      await marketplaceApi.deleteOrderMessage(activeChatOrder, message.id, scope)
      setChatMessages((current) => scope === 'me'
        ? current.filter((item) => item.id !== message.id)
        : current.map((item) => item.id === message.id ? { ...item, message: '', is_deleted: true } : item))
      const updatedConversations = await marketplaceApi.getConversations()
      setChatConversations(updatedConversations)
      setOrders(updatedConversations)
    } catch (error) {
      setChatLoadError(errorMessage(error))
    }
  }

  const appendChatEmoji = (emoji) => {
    setChatText((current) => `${current}${emoji}`)
    setEmojiPickerOpen(false)
  }

  const renderMessages = () => {
    const chatOrders = orders
    const activeConversation = chatOrders.find((order) => order.id === activeChatOrder)
    return <>
      <section className="mp-chat-shell" aria-label="Farmer and buyer conversations">
        {loading ? <Loading /> : !chatOrders.length ? <div className="mp-chat-empty"><span aria-hidden="true">✉</span><h2>No conversations yet</h2><p>Conversations appear here when you share a marketplace order with a farmer or buyer.</p></div> : <div className={`mp-chat-layout${chatSidebarOpen ? '' : ' mp-chat-layout--conversation'}`}>
          <aside className="mp-chat-sidebar" aria-label="Conversation list">
            <div className="mp-chat-sidebar-heading"><div><span className="mp-eyebrow">Marketplace</span><h2>Messages</h2></div><span className="mp-chat-count">{chatOrders.length}</span></div>
            <div className="mp-chat-conversation-list">
              {chatOrders.map((conversation) => {
                const latest = conversation.latest_message
                const preview = latest?.is_deleted ? 'Message deleted' : latest?.message || `${conversation.crop || 'Order'} · ${conversation.status || 'active'}`
                return <button type="button" className={`mp-chat-conversation${conversation.id === activeChatOrder ? ' mp-chat-conversation--active' : ''}`} key={conversation.id} onClick={() => {
                  setChatMessages([])
                  setChatLoadError('')
                  setChatText('')
                  chatWasNearBottom.current = true
                  setChatReply(null)
                  setEmojiPickerOpen(false)
                  setChatActionMenu('')
                  setChatSidebarOpen(false)
                  setActiveChatOrder(conversation.id)
                  setSearchParams({ tab: 'messages', orderId: conversation.id })
                }}>
                  <span className="mp-chat-avatar">{conversation.counterpart_avatar ? <img src={conversation.counterpart_avatar} alt="" /> : conversation.counterpart_name?.slice(0, 1)?.toUpperCase() || (isBuyer ? 'F' : 'B')}</span>
                  <span className="mp-chat-conversation-copy"><strong>{conversation.counterpart_name || (isBuyer ? 'Farmer' : 'Buyer')}</strong><small>{preview}</small></span>
                  <time>{chatTimeLabel(latest?.created_at || conversation.created_at)}</time>
                </button>
              })}
            </div>
          </aside>
          <section className="mp-chat-main" aria-label="Selected conversation">
            {activeConversation ? <>
              <header className="mp-chat-header">
                <button className="mp-chat-back" type="button" aria-label="Back to conversations" title="Back to conversations" onClick={() => setChatSidebarOpen(true)}>‹</button>
                <span className="mp-chat-avatar">{activeConversation.counterpart_avatar ? <img src={activeConversation.counterpart_avatar} alt="" /> : activeConversation.counterpart_name?.slice(0, 1)?.toUpperCase() || (isBuyer ? 'F' : 'B')}</span>
                <div><strong>{activeConversation.counterpart_name || (isBuyer ? 'Farmer' : 'Buyer')}</strong><small>{activeConversation.crop || 'Marketplace order'} · #{activeConversation.id.slice(-8).toUpperCase()}</small></div>
              </header>
              {chatLoadError && <p role="alert" className="mp-chat-error">{chatLoadError}</p>}
              <div className="mp-chat-history" aria-live="polite" ref={chatHistoryRef} onScroll={(event) => {
                const element = event.currentTarget
                chatWasNearBottom.current = element.scrollHeight - element.scrollTop - element.clientHeight < 96
              }}>
                {chatLoading && !chatMessages.length ? <p className="mp-chat-state">Loading messages...</p> : chatMessages.length ? chatMessages.map((message, index) => {
                  const previous = chatMessages[index - 1]
                  const showDay = !previous || chatDayLabel(previous.created_at) !== chatDayLabel(message.created_at)
                  const mine = message.sender_id === user?.id
                  return <React.Fragment key={message.id}>
                    {showDay && <div className="mp-chat-day"><span>{chatDayLabel(message.created_at)}</span></div>}
                    <article className={`mp-chat-message${mine ? ' mp-chat-message--mine' : ''}${message.is_deleted ? ' mp-chat-message--deleted' : ''}`}>
                      {message.reply_to_id && <div className="mp-chat-reply-preview"><strong>{message.reply_to_sender_name || 'Reply'}</strong><span>{message.reply_to_message}</span></div>}
                      {message.is_deleted ? <p className="mp-chat-deleted-copy">This message was deleted</p> : <p>{message.message}</p>}
                      <div className="mp-chat-message-footer"><time>{chatTimeLabel(message.created_at)}</time>{!message.is_deleted && <button type="button" className="mp-chat-menu-trigger" aria-label="Message actions" title="Message actions" onClick={() => setChatActionMenu(chatActionMenu === message.id ? '' : message.id)}>⋯</button>}</div>
                      {chatActionMenu === message.id && <div className="mp-chat-message-menu">
                        <button type="button" onClick={() => { navigator.clipboard?.writeText(message.message).then(() => setChatActionMenu('')).catch(() => setChatLoadError('Could not copy this message.')) }}>Copy</button>
                        <button type="button" onClick={() => { setChatReply(message); setChatActionMenu('') }}>Reply</button>
                        <button type="button" onClick={() => deleteChatMessage(message, 'me')}>Delete for me</button>
                        {mine && <button type="button" onClick={() => deleteChatMessage(message, 'everyone')}>Delete for everyone</button>}
                      </div>}
                    </article>
                  </React.Fragment>
                }) : <p className="mp-chat-state">No messages yet. Say hello to start the conversation.</p>}
                <div ref={chatEndRef} />
              </div>
              <form className="mp-chat-compose" onSubmit={sendChatMessage}>
                {chatReply && <div className="mp-chat-replying"><span><strong>Replying to {chatReply.sender_name}</strong><small>{chatReply.message}</small></span><button type="button" aria-label="Cancel reply" onClick={() => setChatReply(null)}>×</button></div>}
                {emojiPickerOpen && <div className="mp-chat-emoji-picker" aria-label="Emoji picker">{chatEmojis.map((emoji) => <button key={emoji} type="button" onClick={() => appendChatEmoji(emoji)}>{emoji}</button>)}</div>}
                <VirtualKeyboard key={activeChatOrder} value={chatText} onChange={setChatText} inputRef={chatInputRef} />
                <div className="mp-chat-compose-row"><button className="mp-chat-tool" type="button" aria-label="Choose emoji" title="Choose emoji" onClick={() => setEmojiPickerOpen((current) => !current)}>☺</button><textarea ref={chatInputRef} aria-label="Message" rows="1" maxLength="2000" value={chatText} onChange={(event) => setChatText(event.target.value)} onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault()
                    event.currentTarget.form?.requestSubmit()
                  }
                }} placeholder="Write a message..." /><VoiceInputButton key={activeChatOrder} value={chatText} onChange={setChatText} inputRef={chatInputRef} /><button className="mp-chat-send" type="submit" aria-label={chatSending ? 'Sending message' : 'Send message'} title="Send message" disabled={!chatText.trim() || chatSending}>{chatSending ? '…' : '➤'}</button></div>
              </form>
            </> : <div className="mp-chat-state mp-chat-pick-conversation">Choose a conversation to view messages.</div>}
          </section>
        </div>}
      </section>
    </>
  }

  const renderMain = () => {
    if (tab === 'profile' && isBuyer) return renderBuyerProfile()
    if (tab === 'farmers' && isBuyer) return renderFarmers()
    if (tab === 'farmerProfile' && isBuyer) return renderPublicFarmerProfile()
    if (tab === 'notifications' && isBuyer) return renderNotifications()
    if (tab === 'messages') return renderMessages()
    if (tab === 'postRequirement') return renderRequirementForm()
    if (tab === 'listProduce') return renderProduceForm()
    if (tab === 'requirements' || tab === 'myRequirements') return renderMyRequirements()
    if (tab === 'orders' || tab === 'incomingOrders') return renderOrders()
    if (tab === 'dashboard' && isBuyer) return renderDashboard()
    if (tab === 'myProduce') return renderMyProduce()
    return renderProduce()
  }

  return (
    <Background>
      <Navbar />
      <main className="page-content marketplace-page animate-fade-in">
        <div className="mp-topbar">
          <div className="mp-brand"><span>🌾</span><strong>{t('brand.projectName')}</strong><small>Farmer–Buyer Marketplace</small></div>
          <div className="mp-top-actions">
            {isBuyer && <button className="mp-secondary-btn" onClick={() => navigateTab('myRequirements')}>My Requirements</button>}
          </div>
        </div>
        <nav className="mp-tabs" aria-label="Marketplace navigation">
          {tabs.map((item) => <button type="button" key={item.id} className={tab === item.id || item.id === 'requirements' && tab === 'myRequirements' ? 'mp-tab mp-tab--active' : 'mp-tab'} onClick={() => chooseTab(item.id)}>{item.label}</button>)}
        </nav>
        {notice && <div role="status" className={`mp-notice mp-notice--${notice.kind}`}>{notice.text}<button onClick={() => setNotice(null)} aria-label="Dismiss notification">×</button></div>}
        {renderMain()}
        {orderingListing && <div className="mp-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !saving) setOrderingListing(null) }}>
          <section className="mp-order-modal" role="dialog" aria-modal="true" aria-labelledby="mp-order-title">
            <div className="mp-section-heading"><div><span className="mp-eyebrow">Direct marketplace order</span><h2 id="mp-order-title">Order {orderingListing.crop}</h2><p>{orderingListing.farmer_name || 'Local farmer'} · {orderingListing.location}</p></div><button className="mp-secondary-btn" type="button" disabled={saving} onClick={() => setOrderingListing(null)} aria-label="Close order form">×</button></div>
            <div className="mp-order-price"><span>{formatRupees(orderingListing.price_per_unit)} / {displayUnit(orderingListing.unit)}</span><span>{displayQuantity(orderingListing.quantity, orderingListing.unit)} {mt('availableQuantityLabel')}</span></div>
            <form className="mp-form-grid" onSubmit={submitListingOrder}>
              <Field label={`${mt('quantity')} (${displayUnit(orderingListing.unit)})`} type="number" min="0.01" max={orderingListing.quantity} step="any" value={listingOrderForm.quantity} required onChange={(value) => setListingOrderForm({ ...listingOrderForm, quantity: value })} />
              <div className="mp-budget"><span>Estimated total</span><strong>{formatRupees(Number(listingOrderForm.quantity || 0) * Number(orderingListing.price_per_unit))}</strong><small>Final price is verified by the server.</small></div>
              <Field label="Delivery location" value={listingOrderForm.delivery_location} required onChange={(value) => setListingOrderForm({ ...listingOrderForm, delivery_location: value })} />
              <Field label="Delivery address" value={listingOrderForm.delivery_address} onChange={(value) => setListingOrderForm({ ...listingOrderForm, delivery_address: value })} />
              <Field label="Preferred delivery date" type="date" min={new Date().toISOString().slice(0, 10)} value={listingOrderForm.delivery_date} required onChange={(value) => setListingOrderForm({ ...listingOrderForm, delivery_date: value })} />
              <label className="mp-field mp-field--wide"><span>Optional message to the farmer</span><textarea rows="3" maxLength="1500" value={listingOrderForm.message} onChange={(event) => setListingOrderForm({ ...listingOrderForm, message: event.target.value })} /></label>
              <div className="mp-form-actions mp-field--wide"><GradientButton type="submit" loading={saving}>Submit Order</GradientButton><button className="mp-secondary-btn" type="button" disabled={saving} onClick={() => setOrderingListing(null)}>Cancel</button></div>
            </form>
          </section>
        </div>}
        {requestingFarmerOrder && publicFarmer && <div className="mp-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !saving) setRequestingFarmerOrder(false) }}>
          <section className="mp-order-modal" role="dialog" aria-modal="true" aria-labelledby="mp-farmer-request-title">
            <div className="mp-section-heading"><div><span className="mp-eyebrow">Pending farmer review</span><h2 id="mp-farmer-request-title">Send an order request</h2><p>Requesting produce is not a confirmed listing or order until the farmer accepts.</p></div><button className="mp-secondary-btn" type="button" disabled={saving} onClick={() => setRequestingFarmerOrder(false)} aria-label="Close order request form">×</button></div>
            <form className="mp-form-grid" onSubmit={submitFarmerOrderRequest}>
              <label className="mp-field mp-field--wide"><span>{mt('availableListingOptional')}</span><select value={farmerOrderRequestForm.listing_id} onChange={(event) => updateFarmerOrderRequestListing(event.target.value)}><option value="">{mt('noSpecificListing')}</option>{publicFarmer.listings.map((listing) => <option key={listing.id} value={listing.id}>{translatePlantVillageCrop(listing.crop, t)} · {displayQuantity(listing.quantity, listing.unit)} {mt('availableQuantityLabel')}</option>)}</select><small>{mt('listingPendingHint')}</small></label>
              <Field label="Crop or product" value={farmerOrderRequestForm.crop} required onChange={(value) => setFarmerOrderRequestForm({ ...farmerOrderRequestForm, crop: value })} />
              <Field label="Requested quantity" type="number" min="0.01" step="any" value={farmerOrderRequestForm.quantity} required onChange={(value) => setFarmerOrderRequestForm({ ...farmerOrderRequestForm, quantity: value })} />
              <SelectField label={mt('unit')} value={farmerOrderRequestForm.unit} options={localizedUnits} onChange={(value) => setFarmerOrderRequestForm({ ...farmerOrderRequestForm, unit: value })} />
              <Field label="Offered price per unit (₹)" type="number" min="0.01" step="any" value={farmerOrderRequestForm.price_per_unit} required onChange={(value) => setFarmerOrderRequestForm({ ...farmerOrderRequestForm, price_per_unit: value })} />
              <Field label="Delivery location" value={farmerOrderRequestForm.delivery_location} required onChange={(value) => setFarmerOrderRequestForm({ ...farmerOrderRequestForm, delivery_location: value })} />
              <Field label="Required delivery date" type="date" min={new Date().toISOString().slice(0, 10)} value={farmerOrderRequestForm.delivery_date} required onChange={(value) => setFarmerOrderRequestForm({ ...farmerOrderRequestForm, delivery_date: value })} />
              <label className="mp-field mp-field--wide"><span>Optional message to the farmer</span><textarea rows="3" maxLength="1500" value={farmerOrderRequestForm.message} onChange={(event) => setFarmerOrderRequestForm({ ...farmerOrderRequestForm, message: event.target.value })} /></label>
              <div className="mp-form-actions mp-field--wide"><GradientButton type="submit" loading={saving}>Submit Order Request</GradientButton><button className="mp-secondary-btn" type="button" disabled={saving} onClick={() => setRequestingFarmerOrder(false)}>Cancel</button></div>
            </form>
          </section>
        </div>}
      </main>
    </Background>
  )
}

const Field = ({ label, value, onChange, type = 'text', required = false, placeholder = '', ...props }) => (
  <label className="mp-field"><span>{label}{required && <b> *</b>}</span><input type={type} value={value ?? ''} onChange={(event) => onChange(event.target.value)} required={required} placeholder={placeholder} {...props} /></label>
)
const SelectField = ({ label, value, options, onChange }) => (
  <label className="mp-field"><span>{label}</span><select value={value} onChange={(event) => onChange(event.target.value)}>{options.map((option) => {
    const normalized = typeof option === 'object' ? option : { value: option, label: option }
    return <option key={normalized.value || 'all'} value={normalized.value}>{normalized.label || 'All categories'}</option>
  })}</select></label>
)
const Fact = ({ label, value }) => <div className="mp-fact"><span>{label}</span><strong>{value || '—'}</strong></div>
const Loading = () => <div className="mp-loading"><span className="loading-spinner" /> Loading marketplace data…</div>
const EmptyState = ({ title, text, action, actionText }) => (
  <GlassCard className="mp-empty"><span aria-hidden="true">🌿</span><h3>{title}</h3><p>{text}</p>{action && <GradientButton onClick={action}>{actionText}</GradientButton>}</GlassCard>
)

export default Marketplace
